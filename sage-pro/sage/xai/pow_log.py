import hashlib
import time
import json
import structlog
from typing import Dict, Any

logger = structlog.get_logger(__name__)

class ProofOfWorkLogger:
    """Creates a cryptographically linked chain of reasoning steps.

    Each step is hashed and linked to the parent hash, ensuring that the 
    reasoning trajectory has not been tampered with post-inference.
    """

    def __init__(self) -> None:
        self.last_hash = "0" * 64

    def commit_step(self, node_name: str, artifact: Any) -> Dict[str, Any]:
        """Hashes an artifact and links it to the chain.

        Args:
            node_name: The name of the reasoning node (e.g. "synthesize").
            artifact: The content produced by the node.

        Returns:
            A dictionary representing the PoW entry.
        """
        content_str = str(artifact)
        current_timestamp = time.time()
        
        # Calculate SHA-256 hash of (node + timestamp + content + parent_hash)
        input_str = f"{node_name}{current_timestamp}{content_str}{self.last_hash}"
        current_hash = hashlib.sha256(input_str.encode()).hexdigest()
        
        entry = {
            "node": node_name,
            "timestamp": current_timestamp,
            "hash": current_hash,
            "parent_hash": self.last_hash
        }
        
        self.last_hash = current_hash
        logger.info("pow_step_committed", node=node_name, hash_prefix=current_hash[:8])
        
        return entry
