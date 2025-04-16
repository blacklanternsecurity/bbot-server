#! /bin/bash

# delete the default agent if it exists
bbctl agent delete --name "Docker Default Agent"

# create the default agent
default_agent_json=$(bbctl agent create --name "Docker Default Agent" --description "Default agent for Docker")

# get the id and name of the default agent
default_agent_id=$(echo "$default_agent_json" | jq -r '.id')
default_agent_name=$(echo "$default_agent_json" | jq -r '.name')

# start the agent
bbctl agent start --id "$default_agent_id" --name "$default_agent_name"
