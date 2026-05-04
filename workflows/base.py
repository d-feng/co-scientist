"""Base class for all Co-scientist workflows."""
from abc import ABC, abstractmethod
import sys


class BaseWorkflow(ABC):
    name: str = "Unnamed"
    description: str = ""
    icon: str = ""

    # Override in subclass or set via UI.  Empty string → use sys.executable.
    python_bin: str = ""

    def get_python_bin(self) -> str:
        """Return the Python interpreter to use for this workflow."""
        return self.python_bin.strip() or sys.executable

    @abstractmethod
    def build_input_panel(self, parent):
        """Build and return the workflow-specific input frame."""

    @abstractmethod
    def get_prompt(self) -> str:
        """Return the final prompt string to send to the agent."""

    @abstractmethod
    def get_run_script(self, model: str, data_dir: str, timeout: int,
                       skip_datalake: bool, full_prompt: str) -> str:
        """Return a Python script string that runs the workflow."""

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return dict with keys: gene, preset for memory storage."""
