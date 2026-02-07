"""
Weights & Biases (wandb) utilities for MLIP Agent

This module provides utilities for integrating wandb logging into MLIP training workflows.
"""

import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

# Try to import wandb
WANDB_AVAILABLE = False
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    logger.warning("wandb is not installed. Wandb logging will be disabled.")
    WANDB_AVAILABLE = False


def init_wandb(
    project: Optional[str] = None,
    entity: Optional[str] = None,
    name: Optional[str] = None,
    tags: Optional[list] = None,
    config: Optional[Dict[str, Any]] = None,
    resume: Optional[str] = None,
    mode: Optional[str] = None
) -> Optional[Any]:
    """
    Initialize a wandb run.
    
    Args:
        project: Name of the wandb project. If None, uses default or creates new project.
        entity: Name of the wandb entity (username or team).
        name: Name of the run. If None, wandb will generate one.
        tags: List of tags for the run.
        config: Dictionary of configuration parameters to log.
        resume: Resume mode ("allow", "must", "never", or run_id).
        mode: Wandb mode ("online", "offline", "disabled").
    
    Returns:
        wandb run object if wandb is available, None otherwise.
    """
    if not WANDB_AVAILABLE:
        logger.warning("wandb is not available. Skipping wandb initialization.")
        return None
    
    # Check if wandb is disabled via environment variable
    if mode is None:
        mode = os.environ.get("WANDB_MODE", "online")
    
    if mode == "disabled":
        logger.info("wandb is disabled via mode setting.")
        return None
    
    # Set default project if not provided
    if project is None:
        project = os.environ.get("WANDB_PROJECT", "base-agent")
    
    # Initialize wandb run
    run = wandb.init(
        project=project,
        entity=entity,
        name=name,
        tags=tags,
        config=config,
        resume=resume,
        mode=mode
    )
    
    logger.info(f"Initialized wandb run: {run.name} in project: {project}")
    return run


def log_training_metrics(
    epoch: int,
    metrics: Dict[str, float],
    prefix: str = ""
) -> None:
    """
    Log training metrics to wandb.
    
    Args:
        epoch: Current epoch number.
        metrics: Dictionary of metrics to log (e.g., {"loss": 0.5, "energy_mae": 0.01}).
        prefix: Optional prefix for metric names (e.g., "train", "val").
    """
    if not WANDB_AVAILABLE:
        return
    
    if wandb.run is None:
        logger.warning("wandb run not initialized. Skipping metric logging.")
        return
    
    # Add prefix to metric names
    log_dict = {}
    for key, value in metrics.items():
        if prefix:
            log_key = f"{prefix}/{key}" if "/" not in key else f"{prefix}_{key}"
        else:
            log_key = key
        
        # Handle None values
        if value is not None:
            log_dict[log_key] = value
    
    # Log metrics with epoch
    if log_dict:
        wandb.log(log_dict, step=epoch)


def log_training_history(
    training_history: Dict[str, Any],
    model_name: str,
    final_metrics: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log complete training history to wandb.
    
    Args:
        training_history: Dictionary containing training history with keys like:
            - energy_mae_train, energy_mae_val
            - force_mae_train, force_mae_val
            - stress_mae_train, stress_mae_val
            - loss_train, loss_val
        model_name: Name of the model being trained.
        final_metrics: Optional dictionary of final metrics to log as summary.
    """
    if not WANDB_AVAILABLE:
        return
    
    if wandb.run is None:
        logger.warning("wandb run not initialized. Skipping training history logging.")
        return
    
    # Log model name as a tag
    wandb.run.tags = wandb.run.tags or []
    if model_name not in wandb.run.tags:
        wandb.run.tags.append(model_name)
        wandb.run.tags = list(set(wandb.run.tags))  # Remove duplicates
    
    # Log training metrics epoch by epoch
    max_epochs = 0
    
    # Find maximum epoch length
    for key in ['energy_mae_train', 'energy_mae_val', 'force_mae_train', 'force_mae_val',
                'stress_mae_train', 'stress_mae_val', 'loss_train', 'loss_val']:
        if key in training_history:
            values = [x for x in training_history[key] if x is not None]
            if len(values) > max_epochs:
                max_epochs = len(values)
    
    # Log metrics for each epoch
    for epoch in range(max_epochs):
        metrics = {}
        
        # Energy MAE (convert to meV/atom if needed)
        if 'energy_mae_train' in training_history and epoch < len(training_history['energy_mae_train']):
            val = training_history['energy_mae_train'][epoch]
            if val is not None:
                # Convert to meV/atom if value is small (likely in eV/atom)
                if val < 10.0:
                    val = val * 1000
                metrics['train/energy_mae'] = val
        
        if 'energy_mae_val' in training_history and epoch < len(training_history['energy_mae_val']):
            val = training_history['energy_mae_val'][epoch]
            if val is not None:
                if val < 10.0:
                    val = val * 1000
                metrics['val/energy_mae'] = val
        
        # Force MAE (convert to meV/Å if needed)
        if 'force_mae_train' in training_history and epoch < len(training_history['force_mae_train']):
            val = training_history['force_mae_train'][epoch]
            if val is not None:
                if val < 1.0:
                    val = val * 1000
                metrics['train/force_mae'] = val
        
        if 'force_mae_val' in training_history and epoch < len(training_history['force_mae_val']):
            val = training_history['force_mae_val'][epoch]
            if val is not None:
                if val < 1.0:
                    val = val * 1000
                metrics['val/force_mae'] = val
        
        # Stress MAE
        if 'stress_mae_train' in training_history and epoch < len(training_history['stress_mae_train']):
            val = training_history['stress_mae_train'][epoch]
            if val is not None:
                metrics['train/stress_mae'] = val
        
        if 'stress_mae_val' in training_history and epoch < len(training_history['stress_mae_val']):
            val = training_history['stress_mae_val'][epoch]
            if val is not None:
                metrics['val/stress_mae'] = val
        
        # Loss
        if 'loss_train' in training_history and epoch < len(training_history['loss_train']):
            val = training_history['loss_train'][epoch]
            if val is not None:
                metrics['train/loss'] = val
        
        if 'loss_val' in training_history and epoch < len(training_history['loss_val']):
            val = training_history['loss_val'][epoch]
            if val is not None:
                metrics['val/loss'] = val
        
        if metrics:
            wandb.log(metrics, step=epoch + 1)
    
    # Log final metrics as summary
    if final_metrics:
        for key, value in final_metrics.items():
            if value is not None:
                wandb.run.summary[key] = value
    
    # Log label distributions as histograms
    if 'energy_distribution' in training_history and training_history['energy_distribution']:
        wandb.log({
            "data/energy_distribution": wandb.Histogram(training_history['energy_distribution'])
        })
    
    if 'force_distribution' in training_history and training_history['force_distribution']:
        wandb.log({
            "data/force_distribution": wandb.Histogram(training_history['force_distribution'])
        })
    
    if 'stress_distribution' in training_history and training_history['stress_distribution']:
        wandb.log({
            "data/stress_distribution": wandb.Histogram(training_history['stress_distribution'])
        })
    
    logger.info(f"Logged training history to wandb for {max_epochs} epochs")


def finish_wandb() -> None:
    """Finish the current wandb run."""
    if not WANDB_AVAILABLE:
        return
    
    if wandb.run is not None:
        wandb.finish()
        logger.info("Finished wandb run")


def parse_wandb_config_from_query(query: str) -> Dict[str, Any]:
    """
    Parse wandb configuration from user query.
    
    This function extracts information about wandb project settings from the user's query.
    It looks for keywords like:
    - "new project", "create project" -> create new project
    - "existing project", "add to project" -> use existing project
    - Project names mentioned in the query
    
    Args:
        query: User's query string.
    
    Returns:
        Dictionary with wandb configuration:
            - project: Project name (or None for default)
            - create_new: Whether to create a new project (True/False/None)
            - tags: List of tags extracted from query
    """
    query_lower = query.lower()
    
    config = {
        "project": None,
        "create_new": None,
        "tags": []
    }
    
    # Check for new project keywords
    if any(keyword in query_lower for keyword in ["new project", "create project", "new wandb project"]):
        config["create_new"] = True
    
    # Check for existing project keywords
    if any(keyword in query_lower for keyword in ["existing project", "add to project", "same project", "continue project"]):
        config["create_new"] = False
    
    # Try to extract project name from query
    # Look for patterns like "project: name" or "wandb project: name"
    import re
    project_patterns = [
        r'project[:\s]+([a-zA-Z0-9_-]+)',
        r'wandb[:\s]+project[:\s]+([a-zA-Z0-9_-]+)',
        r'log[:\s]+to[:\s]+([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in project_patterns:
        match = re.search(pattern, query_lower, re.IGNORECASE)
        if match:
            config["project"] = match.group(1)
            break
    
    # Extract tags from query (look for "tag:" or "#" patterns)
    tag_patterns = [
        r'tag[:\s]+([a-zA-Z0-9_-]+)',
        r'#([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in tag_patterns:
        matches = re.findall(pattern, query_lower, re.IGNORECASE)
        config["tags"].extend(matches)
    
    # Remove duplicates
    config["tags"] = list(set(config["tags"]))
    
    return config
