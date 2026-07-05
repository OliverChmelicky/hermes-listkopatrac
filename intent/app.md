The intent of developing this application is a Hermes agent with tools written in Go language which performs REST API calls to obtain information about time off connections, price and occupancy for supported providers.

User can parametrize point A and point B, time from to. If user specifies just day then search parameter from will be for the whole day.

If user specifies parameter 'to' then agent will search for connections which are able to meet the requirements of to date meaning that it is the time when train will arrive in the final destination.

At the end of the search when all REST APIs are parsed the agent can propose options for user. Criteria are from most important to least:
1. Correct FROM and TO cities
2. Correct dates
3. Final price
4. Total duration time
5. Number of transfers (less is better)

Compare all options and return top N for user. Save searched results to internal memory if user asks about historical roads in specific from - to and price.

# Currency
Each provider can have different currency. Use designated tool to compare currencies and display final currency in eur.