Strategies like least busy can lead to requests not being dispatched if certain conditions aren't met. In this case, we requeue the request message in the rabbit message queue (after some time, allowing the server's metrics to be updated in the meantime, preventing looping over the same request many times).

There is then a timeout mechanism that dictates how long a message can stay in the queue (counted from the first time it's been enqueued, timestamp not reset by subsequent enqueuing). It's given by the `x-message-ttl` feature of rabbitmq queues (associated with the env var `RPC_MESSAGE_EXPIRATION` in the consumer's settings). 

Note: different from the `x-expires` argument, which dictates how long a queue will persist without any activity (i.e: no message in queue and no consumer attached to it)

Since the sender awaits for the consumer response, there needs to be a timeout in the sender's call too, which should match the `x-message-ttl` (the associated env var is `MESSAGE_TIMEOUT` in the sender's settings.
