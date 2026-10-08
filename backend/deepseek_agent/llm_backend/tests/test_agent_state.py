from app.lg_agent.lg_states import AgentState


def test_agent_state_has_iteration_default_zero():
    s = AgentState(messages=[])
    assert s.iteration == 0


def test_agent_state_iteration_settable():
    s = AgentState(messages=[], iteration=3)
    assert s.iteration == 3
