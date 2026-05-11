from .task_workflow import TaskWorkflow

WORKFLOW_REGISTRY = {
    "task": TaskWorkflow,
    "generic": TaskWorkflow, # Generic is now just a TaskWorkflow with no commands
    "none": TaskWorkflow
}
