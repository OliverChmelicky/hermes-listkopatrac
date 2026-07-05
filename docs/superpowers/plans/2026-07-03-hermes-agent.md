# Hermes Search Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dependency-free Go CLI binary (`hermes-search`) that the Hermes agent invokes with flags to search RegioJet for A→B connections and get back ranked, EUR-priced results as JSON.

**Architecture:** `cmd/hermes-search` parses flags into a `SearchQuery` and prints JSON. `pkg/search` runs the pipeline (concurrent provider fan-out → EUR normalization → filter/sort/take-N → assemble `Output`). Providers sit behind an interface so more can be added; RegioJet is the one adapter. No LLM, no conversation — the agent owns all natural-language work.

**Tech Stack:** Go 1.22, standard library only (net/http, encoding/json, flag, testing, httptest).

## Global Constraints

- Go 1.22+, module path `hermes`. Import paths are `hermes/pkg/<name>`.
- **Standard library only** — no third-party dependencies.
- Packages under `pkg/`; the binary under `cmd/hermes-search/`; tool description under `tools/`.
- Default `ResultCount` = 5. RegioJet defaults: `fromLocationId=10202001` (CITY), `toLocationId=372825000` (STATION).
- Currency is EUR throughout v1; `ToEUR` is an identity seam.
- Prices ranked ascending by `PriceEUR` (derived from `PriceFrom`).
- One-shot binary: flags in, single JSON object out on stdout, plain-text errors on stderr.
- TDD: write the failing test first. Commit after each task.

---

### Task 1: Project scaffolding + shared model types

**Files:**
- Create: `go.mod`
- Create: `pkg/model/model.go`
- Test: `pkg/model/model_test.go`

**Interfaces:**
- Consumes: nothing.
- Produces: `model.SearchQuery`, `model.Connection`, `model.Option` (all with JSON tags), the `Default*` constants, and `SearchQuery.WithDefaults() SearchQuery`.

- [ ] **Step 1: Initialize the module**

Run:
```bash
cd /home/olo/pp/listkoPatrac && go mod init hermes && go version
```
Expected: creates `go.mod` with `module hermes` and a `go 1.2x` line.

- [ ] **Step 2: Write the failing test**

Create `pkg/model/model_test.go`:
```go
package model

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestWithDefaultsFillsEmptyFields(t *testing.T) {
	got := SearchQuery{}.WithDefaults()
	if got.FromLocationID != DefaultFromLocationID {
		t.Errorf("FromLocationID = %q, want %q", got.FromLocationID, DefaultFromLocationID)
	}
	if got.FromLocationType != DefaultFromLocationType {
		t.Errorf("FromLocationType = %q, want %q", got.FromLocationType, DefaultFromLocationType)
	}
	if got.ToLocationID != DefaultToLocationID {
		t.Errorf("ToLocationID = %q, want %q", got.ToLocationID, DefaultToLocationID)
	}
	if got.ToLocationType != DefaultToLocationType {
		t.Errorf("ToLocationType = %q, want %q", got.ToLocationType, DefaultToLocationType)
	}
	if got.ResultCount != DefaultResultCount {
		t.Errorf("ResultCount = %d, want %d", got.ResultCount, DefaultResultCount)
	}
}

func TestWithDefaultsKeepsProvidedValues(t *testing.T) {
	in := SearchQuery{FromLocationID: "999", ResultCount: 2}
	got := in.WithDefaults()
	if got.FromLocationID != "999" || got.ResultCount != 2 {
		t.Errorf("provided values overwritten: %+v", got)
	}
}

func TestOptionJSONHasPromotedFieldsAndPriceEUR(t *testing.T) {
	o := Option{Connection: Connection{Provider: "RegioJet", PriceFrom: 16.9}, PriceEUR: 16.9}
	b, err := json.Marshal(o)
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	if !strings.Contains(s, `"provider":"RegioJet"`) || !strings.Contains(s, `"priceEUR":16.9`) {
		t.Errorf("unexpected JSON: %s", s)
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `go test ./pkg/model/`
Expected: FAIL — undefined `SearchQuery`, `WithDefaults`, constants.

- [ ] **Step 4: Write the implementation**

Create `pkg/model/model.go`:
```go
package model

import "time"

const (
	DefaultFromLocationID   = "10202001"
	DefaultFromLocationType = "CITY"
	DefaultToLocationID     = "372825000"
	DefaultToLocationType   = "STATION"
	DefaultResultCount      = 5
)

// SearchQuery is the structured form of a travel request passed to the tool.
type SearchQuery struct {
	FromLocationID   string
	FromLocationType string
	ToLocationID     string
	ToLocationType   string
	DepartureDate    time.Time  // day granularity
	ArriveBy         *time.Time // optional deadline at destination
	ResultCount      int
}

// WithDefaults returns a copy with empty fields filled from the defaults.
func (q SearchQuery) WithDefaults() SearchQuery {
	if q.FromLocationID == "" {
		q.FromLocationID = DefaultFromLocationID
	}
	if q.FromLocationType == "" {
		q.FromLocationType = DefaultFromLocationType
	}
	if q.ToLocationID == "" {
		q.ToLocationID = DefaultToLocationID
	}
	if q.ToLocationType == "" {
		q.ToLocationType = DefaultToLocationType
	}
	if q.ResultCount == 0 {
		q.ResultCount = DefaultResultCount
	}
	return q
}

// Connection is one option returned by a provider, in the provider's currency.
type Connection struct {
	Provider      string    `json:"provider"`
	DepartureTime time.Time `json:"departureTime"`
	ArrivalTime   time.Time `json:"arrivalTime"`
	PriceFrom     float64   `json:"priceFrom"`
	PriceTo       float64   `json:"priceTo"`
	Currency      string    `json:"currency"`
	FreeSeats     int       `json:"freeSeats"`
	Transfers     int       `json:"transfers"`
	TravelTime    string    `json:"travelTime"`
	Bookable      bool      `json:"bookable"`
}

// Option is a Connection with its price normalized to EUR, ready for ranking.
// The embedded Connection's fields are promoted into the JSON object.
type Option struct {
	Connection
	PriceEUR float64 `json:"priceEUR"`
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `go test ./pkg/model/`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add go.mod pkg/model/
git commit -m "feat: module scaffolding and shared model types"
```

---

### Task 2: Currency normalization (identity seam)

**Files:**
- Create: `pkg/currency/currency.go`
- Test: `pkg/currency/currency_test.go`

**Interfaces:**
- Consumes: `model.Connection`, `model.Option`.
- Produces: `currency.ToEUR(model.Connection) model.Option` and `currency.ToEURAll([]model.Connection) []model.Option`.

- [ ] **Step 1: Write the failing test**

Create `pkg/currency/currency_test.go`:
```go
package currency

import (
	"testing"

	"hermes/pkg/model"
)

func TestToEURUsesPriceFrom(t *testing.T) {
	c := model.Connection{PriceFrom: 21.4, PriceTo: 23.1, Currency: "EUR"}
	got := ToEUR(c)
	if got.PriceEUR != 21.4 {
		t.Errorf("PriceEUR = %v, want 21.4", got.PriceEUR)
	}
	if got.PriceFrom != 21.4 {
		t.Errorf("embedded Connection lost: %v", got.PriceFrom)
	}
}

func TestToEURAllPreservesOrderAndCount(t *testing.T) {
	in := []model.Connection{{PriceFrom: 1}, {PriceFrom: 2}}
	got := ToEURAll(in)
	if len(got) != 2 || got[0].PriceEUR != 1 || got[1].PriceEUR != 2 {
		t.Errorf("unexpected result: %+v", got)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./pkg/currency/`
Expected: FAIL — undefined `ToEUR`.

- [ ] **Step 3: Write the implementation**

Create `pkg/currency/currency.go`:
```go
package currency

import "hermes/pkg/model"

// ToEUR normalizes a Connection's price to EUR. In v1 every provider already
// reports EUR, so this is an identity mapping over PriceFrom. When a non-EUR
// provider is added, real conversion happens here.
func ToEUR(c model.Connection) model.Option {
	return model.Option{Connection: c, PriceEUR: c.PriceFrom}
}

// ToEURAll maps ToEUR over a slice, preserving order.
func ToEURAll(cs []model.Connection) []model.Option {
	out := make([]model.Option, len(cs))
	for i, c := range cs {
		out[i] = ToEUR(c)
	}
	return out
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./pkg/currency/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pkg/currency/
git commit -m "feat: EUR currency normalization seam"
```

---

### Task 3: Ranking (filter + sort + take N)

**Files:**
- Create: `pkg/rank/rank.go`
- Test: `pkg/rank/rank_test.go`

**Interfaces:**
- Consumes: `model.Option`, `model.SearchQuery`.
- Produces: `rank.Rank(opts []model.Option, q model.SearchQuery) []model.Option`.

Filtering rules: keep an option only if `Bookable` and `FreeSeats > 0` and `PriceFrom > 0` (drops sold-out rows, which RegioJet reports with `priceFrom: 0`) and — when `q.ArriveBy != nil` — `ArrivalTime <= *q.ArriveBy`. Then sort by `PriceEUR` ascending and return at most `q.ResultCount`.

- [ ] **Step 1: Write the failing test**

Create `pkg/rank/rank_test.go`:
```go
package rank

import (
	"testing"
	"time"

	"hermes/pkg/model"
)

func opt(price float64, bookable bool, seats int, arrive time.Time) model.Option {
	return model.Option{
		Connection: model.Connection{
			PriceFrom:   price,
			Bookable:    bookable,
			FreeSeats:   seats,
			ArrivalTime: arrive,
		},
		PriceEUR: price,
	}
}

func TestRankFiltersSortsAndLimits(t *testing.T) {
	base := time.Date(2026, 7, 4, 8, 0, 0, 0, time.UTC)
	in := []model.Option{
		opt(30, true, 5, base),
		opt(0, false, 0, base), // sold out -> dropped
		opt(10, true, 3, base),
		opt(20, true, 2, base),
		opt(15, true, 0, base), // no seats -> dropped
	}
	got := Rank(in, model.SearchQuery{ResultCount: 2})
	if len(got) != 2 {
		t.Fatalf("len = %d, want 2", len(got))
	}
	if got[0].PriceEUR != 10 || got[1].PriceEUR != 20 {
		t.Errorf("wrong order/prices: %v, %v", got[0].PriceEUR, got[1].PriceEUR)
	}
}

func TestRankAppliesArriveBy(t *testing.T) {
	early := time.Date(2026, 7, 4, 9, 0, 0, 0, time.UTC)
	late := time.Date(2026, 7, 4, 18, 0, 0, 0, time.UTC)
	deadline := time.Date(2026, 7, 4, 12, 0, 0, 0, time.UTC)
	in := []model.Option{
		opt(5, true, 1, late),  // after deadline -> dropped
		opt(8, true, 1, early), // ok
	}
	got := Rank(in, model.SearchQuery{ResultCount: 5, ArriveBy: &deadline})
	if len(got) != 1 || got[0].PriceEUR != 8 {
		t.Fatalf("arrive-by filter wrong: %+v", got)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./pkg/rank/`
Expected: FAIL — undefined `Rank`.

- [ ] **Step 3: Write the implementation**

Create `pkg/rank/rank.go`:
```go
package rank

import (
	"sort"

	"hermes/pkg/model"
)

// Rank filters out unbookable/sold-out/too-late options, sorts the survivors
// by EUR price ascending, and returns at most q.ResultCount of them.
func Rank(opts []model.Option, q model.SearchQuery) []model.Option {
	kept := make([]model.Option, 0, len(opts))
	for _, o := range opts {
		if !o.Bookable || o.FreeSeats <= 0 || o.PriceFrom <= 0 {
			continue
		}
		if q.ArriveBy != nil && o.ArrivalTime.After(*q.ArriveBy) {
			continue
		}
		kept = append(kept, o)
	}

	sort.SliceStable(kept, func(i, j int) bool {
		return kept[i].PriceEUR < kept[j].PriceEUR
	})

	if q.ResultCount > 0 && len(kept) > q.ResultCount {
		kept = kept[:q.ResultCount]
	}
	return kept
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./pkg/rank/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pkg/rank/
git commit -m "feat: ranking with filtering, sort, and take-N"
```

---

### Task 4: Provider interface + concurrent registry

**Files:**
- Create: `pkg/provider/provider.go`
- Test: `pkg/provider/provider_test.go`

**Interfaces:**
- Consumes: `model.SearchQuery`, `model.Connection`.
- Produces:
  - `provider.Provider` interface: `Name() string`, `Search(ctx context.Context, q model.SearchQuery) ([]model.Connection, error)`.
  - `provider.Registry` with `Register(p Provider)` and `SearchAll(ctx, q) ([]model.Connection, map[string]int, error)` — runs providers concurrently, returns all connections plus a per-provider raw count map.

- [ ] **Step 1: Write the failing test**

Create `pkg/provider/provider_test.go`:
```go
package provider

import (
	"context"
	"testing"

	"hermes/pkg/model"
)

type stub struct {
	name  string
	conns []model.Connection
}

func (s stub) Name() string { return s.name }
func (s stub) Search(context.Context, model.SearchQuery) ([]model.Connection, error) {
	return s.conns, nil
}

func TestSearchAllAggregatesAndCounts(t *testing.T) {
	reg := &Registry{}
	reg.Register(stub{name: "A", conns: []model.Connection{{Provider: "A"}, {Provider: "A"}}})
	reg.Register(stub{name: "B", conns: []model.Connection{{Provider: "B"}}})

	conns, counts, err := reg.SearchAll(context.Background(), model.SearchQuery{})
	if err != nil {
		t.Fatal(err)
	}
	if len(conns) != 3 {
		t.Errorf("conns = %d, want 3", len(conns))
	}
	if counts["A"] != 2 || counts["B"] != 1 {
		t.Errorf("counts = %+v", counts)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./pkg/provider/`
Expected: FAIL — undefined `Registry`.

- [ ] **Step 3: Write the implementation**

Create `pkg/provider/provider.go`:
```go
package provider

import (
	"context"
	"sync"

	"hermes/pkg/model"
)

// Provider searches one travel operator for connections.
type Provider interface {
	Name() string
	Search(ctx context.Context, q model.SearchQuery) ([]model.Connection, error)
}

// Registry fans a query out over all registered providers concurrently.
type Registry struct {
	providers []Provider
}

func (r *Registry) Register(p Provider) {
	r.providers = append(r.providers, p)
}

// SearchAll queries every provider in parallel. It returns the combined
// connections and a per-provider raw count. The first error encountered is
// returned; connections gathered from other providers are still valid.
func (r *Registry) SearchAll(ctx context.Context, q model.SearchQuery) ([]model.Connection, map[string]int, error) {
	var (
		mu       sync.Mutex
		all      []model.Connection
		counts   = map[string]int{}
		firstErr error
		wg       sync.WaitGroup
	)

	for _, p := range r.providers {
		wg.Add(1)
		go func(p Provider) {
			defer wg.Done()
			conns, err := p.Search(ctx, q)
			mu.Lock()
			defer mu.Unlock()
			if err != nil {
				if firstErr == nil {
					firstErr = err
				}
				return
			}
			all = append(all, conns...)
			counts[p.Name()] = len(conns)
		}(p)
	}
	wg.Wait()

	return all, counts, firstErr
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./pkg/provider/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pkg/provider/
git commit -m "feat: provider interface and concurrent registry"
```

---

### Task 5: RegioJet adapter

**Files:**
- Create: `pkg/provider/regiojet/regiojet.go`
- Create: `pkg/provider/regiojet/testdata/search_response.json` (copy of the sample response)
- Test: `pkg/provider/regiojet/regiojet_test.go`

**Interfaces:**
- Consumes: `model.SearchQuery`, `model.Connection`, implements `provider.Provider`.
- Produces: `regiojet.New() *regiojet.Client`; `Client{BaseURL string; HTTP *http.Client}`; `Name() string` returns `"RegioJet"`; `Search(ctx, q) ([]model.Connection, error)`.

The adapter maps every route (including sold-out ones with `priceFrom: 0`); filtering is `rank`'s job. It sends `X-Currency: EUR`.

- [ ] **Step 1: Create the fixture**

Run:
```bash
mkdir -p pkg/provider/regiojet/testdata && cp response.json pkg/provider/regiojet/testdata/search_response.json
```
Expected: the sample response from the repo root is copied into `testdata/`.

- [ ] **Step 2: Write the failing test**

Create `pkg/provider/regiojet/regiojet_test.go`:
```go
package regiojet

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"hermes/pkg/model"
)

func TestSearchMapsRoutes(t *testing.T) {
	fixture, err := os.ReadFile("testdata/search_response.json")
	if err != nil {
		t.Fatal(err)
	}

	var gotPath, gotCurrency, gotDate string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath = r.URL.Path
		gotCurrency = r.Header.Get("X-Currency")
		gotDate = r.URL.Query().Get("departureDate")
		w.Write(fixture)
	}))
	defer srv.Close()

	c := New()
	c.BaseURL = srv.URL

	date, _ := time.Parse("2006-01-02", "2026-07-03")
	conns, err := c.Search(context.Background(), model.SearchQuery{DepartureDate: date}.WithDefaults())
	if err != nil {
		t.Fatal(err)
	}

	if gotPath != "/routes/search/simple" {
		t.Errorf("path = %q", gotPath)
	}
	if gotCurrency != "EUR" {
		t.Errorf("X-Currency = %q", gotCurrency)
	}
	if gotDate != "2026-07-03" {
		t.Errorf("departureDate = %q", gotDate)
	}
	if len(conns) == 0 {
		t.Fatal("no connections mapped")
	}

	// First route in the fixture is sold out: priceFrom 0, not bookable.
	if conns[0].Bookable || conns[0].PriceFrom != 0 || conns[0].FreeSeats != 0 {
		t.Errorf("sold-out route mapped wrong: %+v", conns[0])
	}
	if conns[0].Provider != "RegioJet" || conns[0].Currency != "EUR" {
		t.Errorf("provider/currency wrong: %+v", conns[0])
	}

	// At least one bookable route with a real price and sane times should exist.
	var haveBookable bool
	for _, cn := range conns {
		if cn.Bookable && cn.PriceFrom > 0 {
			haveBookable = true
			if !cn.ArrivalTime.After(cn.DepartureTime) {
				t.Errorf("times parsed wrong: %+v", cn)
			}
		}
	}
	if !haveBookable {
		t.Error("expected at least one bookable route")
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `go test ./pkg/provider/regiojet/`
Expected: FAIL — undefined `New`.

- [ ] **Step 4: Write the implementation**

Create `pkg/provider/regiojet/regiojet.go`:
```go
package regiojet

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"

	"hermes/pkg/model"
)

const (
	defaultBaseURL = "https://brn-ybus-pubapi.sa.cz/restapi"
	timeLayout     = "2006-01-02T15:04:05.000-07:00"
)

// Client is the RegioJet provider adapter.
type Client struct {
	BaseURL string
	HTTP    *http.Client
}

func New() *Client {
	return &Client{
		BaseURL: defaultBaseURL,
		HTTP:    &http.Client{Timeout: 30 * time.Second},
	}
}

func (c *Client) Name() string { return "RegioJet" }

type apiResponse struct {
	Routes []apiRoute `json:"routes"`
}

type apiRoute struct {
	DepartureTime  string  `json:"departureTime"`
	ArrivalTime    string  `json:"arrivalTime"`
	TransfersCount int     `json:"transfersCount"`
	FreeSeatsCount int     `json:"freeSeatsCount"`
	PriceFrom      float64 `json:"priceFrom"`
	PriceTo        float64 `json:"priceTo"`
	TravelTime     string  `json:"travelTime"`
	Bookable       bool    `json:"bookable"`
}

// Search queries RegioJet's simple route search for the query's departure day
// and maps every route into a model.Connection (no filtering here).
func (c *Client) Search(ctx context.Context, q model.SearchQuery) ([]model.Connection, error) {
	params := url.Values{}
	params.Set("tariffs", "REGULAR")
	params.Set("fromLocationType", q.FromLocationType)
	params.Set("fromLocationId", q.FromLocationID)
	params.Set("toLocationType", q.ToLocationType)
	params.Set("toLocationId", q.ToLocationID)
	params.Set("departureDate", q.DepartureDate.Format("2006-01-02"))
	params.Set("fromLocationName", "")
	params.Set("toLocationName", "")

	endpoint := c.BaseURL + "/routes/search/simple?" + params.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-Currency", "EUR")
	req.Header.Set("Accept", "application/json")

	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("regiojet: status %d", resp.StatusCode)
	}

	var parsed apiResponse
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return nil, err
	}

	conns := make([]model.Connection, 0, len(parsed.Routes))
	for _, r := range parsed.Routes {
		dep, err := time.Parse(timeLayout, r.DepartureTime)
		if err != nil {
			return nil, fmt.Errorf("regiojet: bad departureTime %q: %w", r.DepartureTime, err)
		}
		arr, err := time.Parse(timeLayout, r.ArrivalTime)
		if err != nil {
			return nil, fmt.Errorf("regiojet: bad arrivalTime %q: %w", r.ArrivalTime, err)
		}
		conns = append(conns, model.Connection{
			Provider:      "RegioJet",
			DepartureTime: dep,
			ArrivalTime:   arr,
			PriceFrom:     r.PriceFrom,
			PriceTo:       r.PriceTo,
			Currency:      "EUR",
			FreeSeats:     r.FreeSeatsCount,
			Transfers:     r.TransfersCount,
			TravelTime:    r.TravelTime,
			Bookable:      r.Bookable,
		})
	}
	return conns, nil
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `go test ./pkg/provider/regiojet/`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pkg/provider/regiojet/
git commit -m "feat: RegioJet provider adapter"
```

---

### Task 6: Search pipeline (fan-out + currency + rank + assemble Output)

**Files:**
- Create: `pkg/search/search.go`
- Test: `pkg/search/search_test.go`

**Interfaces:**
- Consumes: `provider.Registry`, `currency.ToEURAll`, `rank.Rank`, `model.SearchQuery`, `model.Option`.
- Produces:
  - `search.Meta{ProvidersQueried []string; ProviderRaw map[string]int; RawCount int; Dropped int; Returned int}`.
  - `search.Output{Options []model.Option; Meta Meta}` (JSON-tagged).
  - `search.Run(ctx context.Context, reg *provider.Registry, q model.SearchQuery) (search.Output, error)`.

`Run` fans out via `reg.SearchAll`, normalizes with `currency.ToEURAll`, ranks with `rank.Rank`, and assembles the `Output`. `RawCount` is the total connections before filtering; `Dropped = RawCount - Returned`. `ProvidersQueried` is the sorted list of provider names from the count map.

- [ ] **Step 1: Write the failing test**

Create `pkg/search/search_test.go`:
```go
package search

import (
	"context"
	"testing"
	"time"

	"hermes/pkg/model"
	"hermes/pkg/provider"
)

type stubProvider struct{}

func (stubProvider) Name() string { return "RegioJet" }
func (stubProvider) Search(context.Context, model.SearchQuery) ([]model.Connection, error) {
	now := time.Date(2026, 7, 4, 8, 0, 0, 0, time.UTC)
	return []model.Connection{
		{Provider: "RegioJet", PriceFrom: 20, Bookable: true, FreeSeats: 5, ArrivalTime: now},
		{Provider: "RegioJet", PriceFrom: 10, Bookable: true, FreeSeats: 5, ArrivalTime: now},
		{Provider: "RegioJet", PriceFrom: 0, Bookable: false, FreeSeats: 0, ArrivalTime: now}, // sold out
	}, nil
}

func TestRunRanksAndReportsMeta(t *testing.T) {
	reg := &provider.Registry{}
	reg.Register(stubProvider{})

	out, err := Run(context.Background(), reg, model.SearchQuery{ResultCount: 5})
	if err != nil {
		t.Fatal(err)
	}

	if len(out.Options) != 2 {
		t.Fatalf("options = %d, want 2 (sold-out dropped)", len(out.Options))
	}
	if out.Options[0].PriceEUR != 10 {
		t.Errorf("cheapest first expected, got %v", out.Options[0].PriceEUR)
	}
	if out.Meta.RawCount != 3 || out.Meta.Returned != 2 || out.Meta.Dropped != 1 {
		t.Errorf("meta counts wrong: %+v", out.Meta)
	}
	if len(out.Meta.ProvidersQueried) != 1 || out.Meta.ProvidersQueried[0] != "RegioJet" {
		t.Errorf("providersQueried = %v", out.Meta.ProvidersQueried)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./pkg/search/`
Expected: FAIL — undefined `Run`.

- [ ] **Step 3: Write the implementation**

Create `pkg/search/search.go`:
```go
package search

import (
	"context"
	"sort"

	"hermes/pkg/currency"
	"hermes/pkg/model"
	"hermes/pkg/provider"
	"hermes/pkg/rank"
)

// Meta describes how the search was performed, for the agent to narrate.
type Meta struct {
	ProvidersQueried []string       `json:"providersQueried"`
	ProviderRaw      map[string]int `json:"providerRaw"`
	RawCount         int            `json:"rawCount"`
	Dropped          int            `json:"dropped"`
	Returned         int            `json:"returned"`
}

// Output is the full JSON payload emitted by the tool.
type Output struct {
	Options []model.Option `json:"options"`
	Meta    Meta           `json:"meta"`
}

// Run executes the search pipeline: fan out over providers, normalize prices to
// EUR, rank, and assemble the Output with a meta block.
func Run(ctx context.Context, reg *provider.Registry, q model.SearchQuery) (Output, error) {
	conns, counts, err := reg.SearchAll(ctx, q)
	if err != nil {
		return Output{}, err
	}

	opts := currency.ToEURAll(conns)
	ranked := rank.Rank(opts, q)

	names := make([]string, 0, len(counts))
	for name := range counts {
		names = append(names, name)
	}
	sort.Strings(names)

	return Output{
		Options: ranked,
		Meta: Meta{
			ProvidersQueried: names,
			ProviderRaw:      counts,
			RawCount:         len(conns),
			Dropped:          len(conns) - len(ranked),
			Returned:         len(ranked),
		},
	}, nil
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `go test ./pkg/search/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pkg/search/
git commit -m "feat: search pipeline assembling ranked output with meta"
```

---

### Task 7: CLI binary + tool description

**Files:**
- Create: `cmd/hermes-search/main.go`
- Create: `tools/hermes-search.md`

**Interfaces:**
- Consumes: `search.Run`, `provider.Registry`, `regiojet.New`, `model.SearchQuery`.
- Produces: the `hermes-search` binary — parses flags into a `SearchQuery`, runs the pipeline, prints one JSON object to stdout; errors go to stderr with a non-zero exit.

- [ ] **Step 1: Write the entry point**

Create `cmd/hermes-search/main.go`:
```go
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"

	"hermes/pkg/model"
	"hermes/pkg/provider"
	"hermes/pkg/provider/regiojet"
	"hermes/pkg/search"
)

func main() {
	from := flag.String("from", "", "from location ID (default 10202001)")
	fromType := flag.String("from-type", "", "from location type CITY|STATION (default CITY)")
	to := flag.String("to", "", "to location ID (default 372825000)")
	toType := flag.String("to-type", "", "to location type CITY|STATION (default STATION)")
	date := flag.String("date", "", "departure day YYYY-MM-DD (required)")
	arriveBy := flag.String("arrive-by", "", "arrival deadline at destination, RFC3339 (optional)")
	limit := flag.Int("limit", 0, "max options to return (default 5)")
	flag.Parse()

	if *date == "" {
		fmt.Fprintln(os.Stderr, "error: --date is required (YYYY-MM-DD)")
		os.Exit(2)
	}
	depDate, err := time.Parse("2006-01-02", *date)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: bad --date %q: %v\n", *date, err)
		os.Exit(2)
	}

	q := model.SearchQuery{
		FromLocationID:   *from,
		FromLocationType: *fromType,
		ToLocationID:     *to,
		ToLocationType:   *toType,
		DepartureDate:    depDate,
		ResultCount:      *limit,
	}
	if *arriveBy != "" {
		at, err := time.Parse(time.RFC3339, *arriveBy)
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: bad --arrive-by %q: %v\n", *arriveBy, err)
			os.Exit(2)
		}
		q.ArriveBy = &at
	}
	q = q.WithDefaults()

	reg := &provider.Registry{}
	reg.Register(regiojet.New())

	out, err := search.Run(context.Background(), reg, q)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(out); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}
```

- [ ] **Step 2: Build the whole project**

Run: `go build ./...`
Expected: builds with no errors.

- [ ] **Step 3: Run the full test suite and vet**

Run: `go test ./... && go vet ./...`
Expected: all packages PASS; no vet findings.

- [ ] **Step 4: Manual smoke test (real API)**

Run:
```bash
go run ./cmd/hermes-search --date 2026-07-03 --limit 3
```
Expected: a JSON object on stdout with up to 3 ranked options (cheapest first, EUR) and a `meta` block. Requires network access to RegioJet.

- [ ] **Step 5: Write the tool description**

Create `tools/hermes-search.md`:
```markdown
# hermes-search

Searches RegioJet for train/bus connections between two locations on a given day
and returns ranked, EUR-priced options as JSON.

## Usage

    hermes-search --date YYYY-MM-DD [--from ID] [--from-type CITY|STATION] \
                  [--to ID] [--to-type CITY|STATION] [--arrive-by RFC3339] [--limit N]

## Flags

- `--date` (required): departure day, `YYYY-MM-DD`.
- `--from` / `--to`: location IDs. Default `10202001` (CITY) → `372825000` (STATION).
- `--from-type` / `--to-type`: `CITY` or `STATION`. Default `CITY` / `STATION`.
- `--arrive-by` (optional): only keep options arriving at or before this RFC3339
  time at the destination.
- `--limit` (optional): max options to return. Default 5.

## Example

    hermes-search --date 2026-07-03 --from 10202001 --to 372825000 --limit 3

## Output

A JSON object on stdout:

    {
      "options": [
        {
          "provider": "RegioJet",
          "departureTime": "2026-07-04T05:17:00+02:00",
          "arrivalTime": "2026-07-04T09:58:00+02:00",
          "priceFrom": 16.9,
          "priceTo": 29.9,
          "currency": "EUR",
          "freeSeats": 62,
          "transfers": 0,
          "travelTime": "04:41 h",
          "bookable": true,
          "priceEUR": 16.9
        }
      ],
      "meta": {
        "providersQueried": ["RegioJet"],
        "providerRaw": { "RegioJet": 18 },
        "rawCount": 18,
        "dropped": 3,
        "returned": 5
      }
    }

Options are sorted cheapest-first in EUR. Sold-out and unbookable routes are
excluded. On a bad flag the tool prints an error to stderr and exits non-zero.
```

- [ ] **Step 6: Commit**

```bash
git add cmd/hermes-search/ tools/hermes-search.md
git commit -m "feat: hermes-search CLI binary and tool description"
```

---

## Self-Review Notes

- **Spec coverage:** CLI binary with the flag contract (Task 7), provider interface + N-ready fan-out (Task 4), RegioJet adapter with known endpoint/defaults/X-Currency (Task 5), EUR identity seam (Task 2), client-side arrive-by + sold-out filtering + price ranking + take-N=5 (Task 3), pipeline assembling options + meta for agent narration (Task 6), JSON output shape and `tools/` description (Task 7). No LLM/intake/presentation/orchestrator tasks — those belong to the agent, per the revised spec.
- **Type consistency:** `SearchQuery`, `Connection`, `Option`, `Provider`, `Registry.SearchAll(...) ([]Connection, map[string]int, error)`, `search.Output`/`search.Meta`, `search.Run(ctx, *provider.Registry, SearchQuery) (Output, error)` are used identically across tasks.
- **No third-party deps:** every import is standard library or an earlier `hermes/pkg/...` package.
```
