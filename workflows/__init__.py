from .biomni_workflow import BiomniWorkflow
from .geo_sra_workflow import GeoSraWorkflow
from .st_agent_workflow import StAgentWorkflow

WORKFLOWS = [BiomniWorkflow(), GeoSraWorkflow(), StAgentWorkflow()]
