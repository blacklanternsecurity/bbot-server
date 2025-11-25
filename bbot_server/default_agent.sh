#! /bin/bash
set -euo pipefail

agent_name="${BBOT_AGENT_NAME:-Docker Default Agent}"
agent_description="${BBOT_AGENT_DESCRIPTION:-Default agent for Docker}"
delete_existing="${BBOT_AGENT_DELETE_EXISTING:-true}"
neo4j_output="${BBOT_AGENT_NEO4J_OUTPUT:-false}"

if [[ "$delete_existing" == "true" ]]; then
  if ! bbctl agent delete "$agent_name"; then
    echo "Agent $agent_name not found; continuing"
  fi
fi

agent_json=$(bbctl agent create --name "$agent_name" --description "$agent_description")
agent_id=$(echo "$agent_json" | jq -r '.id')
agent_name=$(echo "$agent_json" | jq -r '.name')

start_cmd=(bbctl agent start --id "$agent_id" --name "$agent_name")
if [[ "$neo4j_output" == "true" ]]; then
  start_cmd+=(--neo4j-output)
fi

"${start_cmd[@]}"
