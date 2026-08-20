"""Flow factory functions for easy creation."""

from typing import Any, Dict, List, Optional, Callable

from flomind.core.flow import Flow, NodeType
from flomind.agents.agent import Agent
from flomind.agents.team import Team, TeamStrategy
from flomind.tools.tool import Tool


def create_flow(
    name: str,
    nodes: Optional[Dict[str, Callable]] = None,
    edges: Optional[List[tuple]] = None,
    description: str = "",
    **kwargs
) -> Flow:
    """
    Factory function to create a Flow easily.
    
    Args:
        name: Flow name
        nodes: Dict of {node_id: function}
        edges: List of (source, target[, condition]) tuples
        description: Flow description
        
    Returns:
        Compiled Flow instance
        
    Example:
        >>> flow = create_flow(
        ...     name="my_flow",
        ...     nodes={"process": my_func},
        ...     edges=[("start", "process"), ("process", "end")]
        ... )
    """
    flow = Flow(name=name, description=description)
    
    # Add start node
    flow.add_node("start", NodeType.START, "Start")
    
    # Add task nodes
    if nodes:
        for node_id, func in nodes.items():
            flow.add_node(
                node_id,
                NodeType.TASK,
                node_id,
                func=func
            )
            
    # Add end node
    flow.add_node("end", NodeType.END, "End")
    
    # Add edges
    if edges:
        for edge in edges:
            if len(edge) == 2:
                flow.add_edge(edge[0], edge[1])
            elif len(edge) == 3:
                flow.add_edge(edge[0], edge[1], condition=edge[2])
                
    return flow.compile()


def create_agent(
    name: str,
    role: str = "assistant",
    system_prompt: str = "",
    tools: Optional[List[Tool]] = None,
    model: str = "gpt-4",
    **kwargs
) -> Agent:
    """
    Factory function to create an Agent easily.
    
    Args:
        name: Agent name
        role: Agent role/title
        system_prompt: System prompt for the agent
        tools: List of tools available to the agent
        model: LLM model to use
        
    Returns:
        Configured Agent instance
        
    Example:
        >>> agent = create_agent(
        ...     name="Researcher",
        ...     role="researcher",
        ...     tools=[search_tool]
        ... )
    """
    return Agent(
        name=name,
        role=role,
        system_prompt=system_prompt,
        tools=tools,
        model=model,
        **kwargs
    )


def create_team(
    name: str,
    agents: List[Agent],
    strategy: str = "sequential",
    **kwargs
) -> Team:
    """
    Factory function to create a Team easily.
    
    Args:
        name: Team name
        agents: List of Agent instances
        strategy: Execution strategy (sequential, parallel, hierarchical)
        
    Returns:
        Configured Team instance
        
    Example:
        >>> team = create_team(
        ...     name="ResearchTeam",
        ...     agents=[researcher, writer],
        ...     strategy="sequential"
        ... )
    """
    return Team(
        name=name,
        agents=agents,
        strategy=strategy,
        **kwargs
    )
