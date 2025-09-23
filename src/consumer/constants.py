from typing import Literal, TypeAlias

###############################
# QUALITY OF SERVICE POLICIES #
###############################
WARNING_LOG_QOS = "warning-log"
PERFORMANCE_BASED_REQUEUE_QOS = "performance-based-requeue"
PARALLEL_REQUESTS_THRESHOLD_REQUEUE_QOS = "parallel-requests-threshold-requeue"

AllowedQualityOfServicePolicies: TypeAlias = Literal[
    "warning-log", "performance-based-requeue", "parallel-requests-threshold-requeue"
]

######################
# ROUTING STRATEGIES #
######################
LEAST_BUSY = "least-busy"
ROUND_ROBIN = "round-robin"

AllowedRoutingStrategies: TypeAlias = Literal["least-busy", "round-robin"]

#####################
# PRIORITY HANDLERS #
#####################
IGNORE_PRIORITY_HANDLER = "ignore"
VLLM_PRIORITY_HANDLER = "vllm"

AllowedPriorityHandlers: TypeAlias = Literal["ignore", "vllm"]
