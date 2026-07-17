# Hermes personal agent

BUILD:

```
docker build -t hermes-agent -f dockerfile .
```

RUN:

```
docker run -it \
           -v $PWD/hermes-skills:/root/.hermes/skills/ \
           -v $PWD/plugins/<tool>:/root/.hermes/plugins/my-plugin \ # for each tool separate volume?
           -v $PWD/config.yml:/root/.hermes/config.yml \
           -e MY_PLUGIN_API_KEY=... \
           hermes-agent
```

To poke around a running container in another terminal:
```
docker exec -it <container-name-or-id> sh
```

# Add skill to hermes

Add file into skills/ in specific folder specified by category.


# Add plugin

## Structure
Example working structure and required standard is in @tools_example/  
tools.py — this is the code that actually executes when the LLM calls tools
schemas.py — this is what the LLM reads to decide when to call tools
plugin.yaml — This tells Hermes: "I'm a plugin called calculator, I provide tools and hooks." The provides_tools and provides_hooks fields are lists of what the plugin registers.
__init__.py — this wires schemas to handlers

## Adding plugin

Project related plugins are in `.hermes/plugins/`. 
```
hermes plugins                    # interactive toggle (space to check/uncheck)
hermes plugins enable <name>      # add to allow-list
hermes plugins disable <name>     # remove from allow-list + add to disabled
```

### Adding plugin for docker
```
docker run -it \
           -v $PWD/hermes-skills:/root/.hermes/skills/ \
           -v $PWD/plugins/<tool>:/root/.hermes/plugins/my-plugin \ # for each tool separate volume?
           -v $PWD/config.yml:/root/.hermes/config.yml \
           -e MY_PLUGIN_API_KEY=... \
           hermes-agent
````

with config.yaml containing:
```
yamlplugins:
  enabled:
    - my-plugin
```    



# Ideas

1. Automaticky pridavat data sources pre Pravobot
2. Ocovi zautomatizovat komunikaciu s klientami v AirB&B


# TODO

1. Run a otestuj skill
2. Run a otestuj config (telegram, model)
3. Pouzivaj plugin na vyhladanie spojenia