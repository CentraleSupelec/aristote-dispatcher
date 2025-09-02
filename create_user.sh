#!/bin/bash

set -e

show_help() {
    cat << EOF
Usage:
  $(basename "$0") --token TOKEN --priority PRIORITY --threshold THRESHOLD --name "FULL NAME" --organization "ORG" --email "EMAIL" [--client-type TYPE]

Description:
  This script finds the first running Kubernetes pod whose name contains "sender"
  and runs the Typer-based add_user.py script inside it.

Options:
  --token          User token (required)
  --priority       Priority value (integer, required)
  --threshold      Threshold value (integer, required)
  --name           Full name of the user (required)
  --organization   Organization name (required)
  --email          Email address of the user (required)
  --client-type    Client type (optional, leave empty for NULL)

Examples:
  $(basename "$0") \\
      --token abc123 \\
      --priority 1 \\
      --threshold 50 \\
      --name "John Doe" \\
      --organization "Acme Corp" \\
      --email "john.doe@example.com"

EOF
}

# If no arguments or help flag is passed
if [[ $# -eq 0 || "$1" == "--help" || "$1" == "-h" ]]; then
    show_help
    exit 0
fi

# Find the sender pod
sender_pod=$(kubectl get pods --no-headers -o custom-columns=":metadata.name" | grep sender | head -n 1)

if [ -z "$sender_pod" ]; then
    echo "❌ No pod containing 'sender' found."
    exit 1
fi

# Execute the Python Typer script inside the pod
kubectl exec "$sender_pod" -- python /app/add_user.py "$@"
