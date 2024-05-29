# Helm chart for large scale LLM

Deployement of LLM at a large scale using VLL server for inference

Architecture using 
- an API block written in python puting the requests received in
- a rabbitmq queue which 
- a python script reads and send the message to 
- a VLLM inference server container.
- The message are then sent back to the client through rabbitmq

## Prerequisites in the cluster

- Gpu-operator from Nvidia should be installed in order to access the gpus
- Rabbitmq operator should be installed if using the internal rabbitmq cluster (values for the cluster are ing rabbitmq-cluster.yaml)
- ingress-nginx to use the ingress part


External chart : 
- using a mysql/postgresql chart to have a database for the identification tokens

## Documentation for the above mentionned blocks

- For Nginx-ingress : https://docs.nginx.com/nginx-ingress-controller/installation/
- For Nvidia GPU Operator : https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html
- For Rabbitmq cluster operator : https://www.rabbitmq.com/kubernetes/operator/install-operator


## Values

### General
| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `model`               | Model name from HuggingFace                        | `""`  |
| `quantization`        | Quantization alogrithm of the used model           | `""`  |
| `dtype`               | Dtype of the model                                 | `""`  |
| `huggingface_token`   | Token used for pulling models from huggingface     | `""`  |

### Tokens

This should be a list of all the tokens wanted and their respective priority
The highest number token is the first one to be answered.

| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `token`               | String for the token                               | `""`  |
| `priority`            | Priority of the token                              | `1`  |

### Sender

The sender is the python block which reproduces the API and sends the message down to rabbitmq queue.

| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `sender.image.repository`| Repository for the image | `centralesupelec/aristote-dispatcher-sender`  |
| `seneder.image.pullPolicy`| Pull policy for the image| `IfNotPresent`  |
| `sender.image.tag`        | Tag for the image | `latest`  |
| `sender.port`| Port used by the sender port | `8080`|
| `sender.ressources`| Ressources specified for the container | `""` |
| `sender.replicaCount`| Replica count for the sender | `1`|
| `sender.env`| Env vars to ad to the container | `[]`|

### Consumer

The consumer is the python block which pulls messages from the rabbitmq queue and sends them to the inference server.

| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `consumer.image.repository`| Repository for the image | `centralesupelec/aristote-dispatcher-consumer`  |
| `consumer.image.pullPolicy`| Pull policy for the image| `IfNotPresent`  |
| `consumer.image.tag` | Tag for the image | `latest`  |
| `consumer.port`| Port used by the consuer port | `8080`|
| `consumer.ressources`| Ressources specified for the container | `""` |
| `consumer.replicaCount`| Replica count for the consumer | `1`|
| `consumer.env`| Env vars to ad to the container | `[]`|


### Inference server

The inference server is using the GPU for ingereing on the LLM. We are using the vLLM inference server.

| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `inferenceserver.image.repository`| Repository for the image | `vllm/vllm-openai`  |
| `inferenceserver.image.pullPolicy`| Pull policy for the image| `Always`  |
| `inferenceserver.image.tag` | Tag for the image | `latest`  |
| `inferenceserver.port`| Port used by the consuer port | `8000`|
| `inferenceserver.ressources`| Ressources specified for the container, should specifiy the gpus | `""` |
| `inferenceserver.replicaCount`| Replica count for the inferenceserver | `1`|
| `inferenceserver.env`| Env vars to ad to the container | `[]`|


### Rabbitmq

Rabbitmq is used for the queue system in the architecture. We are using the rabbitmq cluster operator to create the cluster. The file is ```rabbitmq.yaml```. It is also compatible with an external rabbitmq cluster.

| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `rabbitmq.enabled`| True is the architecture is using rabbitmq | `True`  |
| `rabbitmq.internal`| Used to specify if it is an internal rabbitmq cluster or not| `True`  |
| `rabbitmq.auth.user` | Username for rabbitmq (if external server) | `""`  |
| `rabbitmq.auth.password`| Password for rabbitmq (if external server) | `""`|
| `rabbitmq.host`| Host for external rabbitmq cluster | `""` |

### Database

Database used by the sender to stock the authentification tokens.

| Name                  | Description                                        | Value |
| --------------------- | -------------------------------------------------- | ----- |
| `database.internal`| Used to specify if the database is in the cluster or not | `True` |
| `database.type`| Used to specify the type of database : mysql or postgresql | `mysql` |
| `database.auth.rootPassword` | Root password for the database | `root` |
| `database.auth.username`| Username for the database | `user`|
| `database.auth.password`| Password for the database access | `password`|
| `database.auth.database`| Database name | `test`|
| `database.host`| Host for the database, if an external database | `""`|
| `database.initdbScriptsConfigMap`| init script for database | `database-config-map` |


### Ingress

The usual template for ingress, to update according to your ingress




