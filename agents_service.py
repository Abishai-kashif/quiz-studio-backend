from agents.extensions.handoff_filters import remove_all_tools
from agents import Agent, ModelSettings, Runner, handoff
from models import QuizList, SourceValidatorOutput, AssessmentQuizQuestion, StudentProgress, MisconductionAnalysis
from gemini_model import model
from tools import web_search
from instructions import (
                            source_validator_instructions,
                            content_generator_instructions, 
                            quiz_generator_instructions, 
                            markdown_generator_instructions,
                            tutor_agent_instructions,
                            assessment_agent_instructions
                        )

base_agent = Agent(
    name="base_agent",
    model=model,
    model_settings=ModelSettings(temperature=0.1)
)

source_validator_agent = base_agent.clone(
    name="source_validator_agent",
    instructions=source_validator_instructions,
    output_type=SourceValidatorOutput,
)

content_generator_agent = base_agent.clone(
    name="content_generator_agent",
    instructions=content_generator_instructions,
    model_settings=ModelSettings(temperature=0.5),
    tools=[web_search]
)

quiz_generator_agent = base_agent.clone(
    name="quiz_generator_agent",
    instructions=quiz_generator_instructions,
    handoff_description="""
        Send queries to me when a quiz needs to be created.
    """,
    output_type=QuizList,
)

markdown_generator_agent = base_agent.clone(
    name="markdown_generator_agent",
    instructions=markdown_generator_instructions,
)

tutor_agent = base_agent.clone(
    name="tutor_agent",
    instructions=tutor_agent_instructions,
    model_settings=ModelSettings(temperature=0.8),
    handoffs=[handoff(agent=quiz_generator_agent, input_filter=remove_all_tools)],
    tools=[content_generator_agent.as_tool(
        tool_name="content_generator_agent",
        tool_description="""
            Use this tool to expand a provided source (URL, short text).
                - Call it when the source is too short, unclear, or lacks detail.
                - Input: the source + instruction (e.g., "explain", "summarize", "create example").
                - Output: clear, concise teachable content (summary, explanation, example, or practice question).
        """
    )]
)

# Enhanced Assessment Agent
assessment_agent = base_agent.clone(
    name="assessment_agent",
    instructions=assessment_agent_instructions,
    model_settings=ModelSettings(temperature=0.3),
    handoff_description="""
        Send queries to me for:
        - Generating adaptive quizzes based on curriculum standards
        - Analyzing student responses and detecting misconceptions
        - Tracking student progress and mastery levels
        - Creating personalized learning recommendations
    """,
    tools=[web_search]
)


# if __name__ == "__main__":
#     result = Runner.run_sync(
#         content_generator_agent,
#         input="hi"
#     )

#     print('>>>>>>>>> ', result)