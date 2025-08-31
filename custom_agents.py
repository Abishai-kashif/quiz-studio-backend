from models import QuizList, SourceValidatorOutput
from agents import Agent, ModelSettings, Runner, enable_verbose_stdout_logging
from gemini_model import model
from tools import web_search
from instructions import source_validator_instructions, content_generator_instructions, quiz_generator_instructions
enable_verbose_stdout_logging()

base_agent = Agent(
    name="base_agent",
    model=model,
    model_settings=ModelSettings(temperature=0.1),
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
    output_type=QuizList,
)

if __name__ == "__main__":
    result = Runner.run_sync(
        content_generator_agent,
        input="hi"
    )

    print('>>>>>>>>> ', result)