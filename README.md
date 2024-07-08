# Helm chart for large scale LLM

Deployement of LLM at a large scale using VLL server for inference.

Architecture using 
- API block written in python
- RabbitMQ priority queue 
- Python script that reads and send the message 
- VLLM inference server container
- Messages are sent back to the client through RabbitMQ

## Prerequisites in the cluster

- [GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html) from Nvidia should be installed in order to access the GPUs
- [RabbitMQ Operator](https://www.rabbitmq.com/kubernetes/operator/install-operator) should be installed if using the internal RabbitMQ cluster (values for the cluster are in rabbitmq-cluster.yaml)
- [ingress-nginx](https://docs.nginx.com/nginx-ingress-controller/installation/) for the ingress

External chart : 
- MySQL/PostgreSQL chart to have a database for identification tokens

## Values

### Models

List of all the models to deploy in the application. It can be multiple models.

| Name                   | Description                                                           | Value                                                   |
|------------------------|-----------------------------------------------------------------------|---------------------------------------------------------|
| `name`*                | Name for the model in the cluster : must be lowercase                 | `""`                                                    |
| `model`*               | Model name from HuggingFace                                           | `""`                                                    |
| `quantization`         | Quantization alogrithm of the used model                              | `""`                                                    |
| `dtype`                | Dtype of the model                                                    | `""`                                                    |
| `gpuMemoryUtilisation` | Maximum GPU memory utilisation for the GPU                            | `0.90`                                                  |
| `huggingface_token`    | Token used for pulling models from huggingface                        | `""`                                                    |
| `replicaCount`         | Replica count for the model                                           | `1`                                                     |
| `ropeScaling`          | Object representing RoPE scaling configuration to apply for the model | `{enabled: false, jsonConfiguration: "{}", theta: ""}`  |

`jsonConfiguration` and `theta` parameters of the `ropeScaling` configuration correspond to `--rope-scaling` and
`--rope-theta` arguments of the [VLLM engine](https://docs.vllm.ai/en/latest/models/engine_args.html).

### PVC

Allows vllm pods to restart without having to download models each time.
The PVC is shared between all vllm instances.

| Name                   | Description                                                           | Value                                                   |
|------------------------|-----------------------------------------------------------------------|---------------------------------------------------------|
| `storageSize`                | Size of PVC                 | `"64Gi"`                                                    |

### Tokens

This should be a list of all the tokens wanted and their respective priority
The highest number token is the first one to be answered. It's their weight rather than their order. 

This is mandatory for an internal database, as it will be used to set up the database. If you are using an external database, you can fill it up by yourself.

| Name         | Description                                          | Value |
|--------------|------------------------------------------------------|-------|
| `token`      | String for the token                                 | `""`  |
| `priority`   | Priority of the token                                | `1`   |
| `threshold`  | Maximum number of request in the queue for the token | `10`  |

### Sender

For more informations on the variables, see in `workers/README.md`.

The sender is the python block which reproduces the API and sends the message down to rabbitmq queue.

| Name                        | Description                                                                                                   | Value                                        |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|----------------------------------------------|
| `sender.image.repository`   | Repository for the image                                                                                      | `centralesupelec/aristote-dispatcher-sender` |
| `seneder.image.pullPolicy`  | Pull policy for the image                                                                                     | `IfNotPresent`                               |
| `sender.image.tag`          | Tag for the image                                                                                             | `latest`                                     |
| `sender.port`               | Port used by the sender port                                                                                  | `8080`                                       |
| `sender.resources`          | resources specified for the container                                                                         | `""`                                         |
| `sender.replicaCount`       | Replica count for the sender                                                                                  | `1`                                          |
| `sender.logLevel`           | Log level for the container :                                                                                 |  `"20"`                                        |
| `sender.env`                | Env vars to ad to the container                                                                               | `[]`                                         |
| `sender.podAnnotations`     | Pod annotations for the sender                                                                                | `{}`                                         |
| `sender.podSecurityContext` | Security context for the pod                                                                                  | `{}`                                         |
| `sender.securityContext`    | Security context for the container                                                                            | `{}`                                         |
| `sender.tolerations`        | Tolerations for the container                                                                                 | `[]`                                         |
| `sender.affinty`            | Node affinity and pod afinity for the pod : used if you want to separate the cpu and the gpu part for example | `{}`                                         |
| `sender.nodeSelector`       | Node selector for the pod                                                                                     | `{}`                                         |
| `sender.rpcReconnectAttempts`       | Number of attemps to reconnect to RPC before setting pod to unhealthy                                                                                     | `10`                                         |

### Consumer

The consumer is the Python block which pulls messages from the RabbitMQ queue and sends them to the inference server.

| Name                          | Description                                                                                                   | Value                                          |
|-------------------------------|---------------------------------------------------------------------------------------------------------------|------------------------------------------------|
| `consumer.image.repository`    | Repository for the image                                                                                      | `centralesupelec/aristote-dispatcher-consumer` |
| `consumer.image.pullPolicy`    | Pull policy for the image                                                                                     | `IfNotPresent`                                 |
| `consumer.image.tag`           | Tag for the image                                                                                             | `latest`                                       |
| `consumer.port`                | Port used by the consuer port                                                                                 | `8080`                                         |
| `consumer.resources`           | resources specified for the container                                                                         | `""`                                           |
| `consumer.replicaCount`        | Replica count for the consumer                                                                                | `1`                                            |
| `consumer.env`                 | Env vars to ad to the container                                                                               | `[]`                                           |
| `consumer.podAnnotations`      | Pod annotations for the sender                                                                                | `{}`                                           |
| `consumer.podSecurityContext`  | Security context for the pod                                                                                  | `{}`                                           |
| `consumer.securityContext`     | Security context for the container                                                                            | `{}`                                           |
| `consumer.tolerations`         | Tolerations for the container                                                                                 | `[]`                                           |
| `consumer.affinty`             | Node affinity and pod afinity for the pod : used if you want to separate the cpu and the gpu part for example | `{}`                                           |
| `consumer.nodeSelector`        | Node selector for the pod                                                                                     | `{}`                                           |
| `consumer.rpcReconnectAttempts`| Number of attemps to reconnect to RPC before setting pod to unhealthy                                                                                     | `10`                                         |
| `consumer.rpcQueueExpiration`| Number of milliseconds to wait before removing queue in RabbitMQ if consumer doesn't respond                                                                                     | `30000`                                         |
| `consumer.useProbes`           | The pod uses routes to communicate its status to Kubernetes                                                                                      | `True`                                         |
| `consumer.probePort`           | Port used for probes (if `useProbes` is set to `True`)                                                                                     | `8081`                                         |



### Inference server

The inference server is using the GPU for ingereing on the LLM. We are using the vLLM inference server.

| Name                               | Description                                                     | Value              |
|------------------------------------|-----------------------------------------------------------------|--------------------|
| `inferenceserver.image.repository` | Repository for the image                                        | `vllm/vllm-openai` |
| `inferenceserver.image.pullPolicy` | Pull policy for the image                                       | `Always`           |
| `inferenceserver.image.tag`        | Tag for the image                                               | `latest`           |
| `inferenceserver.port`             | Port used by the inference serveer                              | `8000`             |
| `inferenceserver.resources`*       | resources specified for the container, should specifiy the gpus | `""`               |
| `inferenceserver.replicaCount`     | Replica count for the inferenceserver                           | `1`                |
| `inferenceserver.env`              | Env vars to ad to the container                                 | `[]`               |


### RabbitMQ

RabbitMQ is used for the queue system in the architecture. We are using the rabbitmq cluster operator to create the cluster. The file is ```rabbitmq.yaml```. It is also compatible with an external rabbitmq cluster.

| Name                     | Description                                                  | Value  |
|--------------------------|--------------------------------------------------------------|--------|
| `rabbitmq.enabled`       | True is the architecture is using rabbitmq                   | `True` |
| `rabbitmq.internal`      | Used to specify if it is an internal rabbitmq cluster or not | `True` |
| `rabbitmq.auth.user`     | Username for rabbitmq (if external server)                   | `""`   |
| `rabbitmq.auth.password` | Password for rabbitmq (if external server)                   | `""`   |
| `rabbitmq.host`          | Host for external rabbitmq cluster                           | `""`   |
| `rabbitmq.monitoring`    | Monitor RabbitMQ using Prometheus (if internal server)       | `False`|

### Database

Database used by the sender to stock the authentification tokens.

| Name                              | Description                                                | Value                 |
|-----------------------------------|------------------------------------------------------------|-----------------------|
| `database.internal`               | Used to specify if the database is in the cluster or not   | `True`                |
| `database.type`                   | Used to specify the type of database : mysql or postgresql | `mysql`               |
| `database.auth.rootPassword`      | Root password for the database                             | `root`                |
| `database.auth.username`          | Username for the database                                  | `user`                |
| `database.auth.password`          | Password for the database access                           | `password`            |
| `database.auth.database`          | Database name                                              | `test`                |
| `database.host`                   | Host for the database, if an external database             | `""`                  |
| `database.initdbScriptsConfigMap` | init script for database                                   | `database-config-map` |


### Ingress

The usual template for ingress, to update according to your ingress
