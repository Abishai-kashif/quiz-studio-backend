import json
from models import Body
from agents import Runner, set_tracing_disabled, enable_verbose_stdout_logging
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from openai.types.responses import ResponseTextDeltaEvent
from helper import Helper
from custom_agents import source_validator_agent, content_generator_agent, quiz_generator_agent

set_tracing_disabled(disabled=True)
enable_verbose_stdout_logging()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
async def root():
    return {"message": "Welcome to the AI Quiz Generator API!"}

@app.post("/generate-quiz")
async def main(body: Body):
    print("\n\nbody >>>>>>>>>>>>>>>>>>> \n", body)
    source = body.source
    # source = body.get("source", "")
    # file = body.get("file", None)

    # content: ContentType = source

    # if (file and source):
    #     return {"error": "Please provide either a source or a file, but not both."}

    # if not content:
    #     content = file

    # if not content:
    #     return {"error": "No source provided."}
    
    # return { 
    #     "status": "success",
    #     "message": "Quiz generated successfully."
    #  }

    is_url = Helper.is_url(text=source) 
    is_valid_source = False

    if (not is_url):
        result = await Runner.run(starting_agent=source_validator_agent, input=source)
        is_valid_source = result.final_output.is_valid

    if (is_url or not is_valid_source):
        result = await Runner.run(starting_agent=content_generator_agent, input=source)
        source = result.final_output

    result = Runner.run_streamed(starting_agent=quiz_generator_agent, input=source)
    

    async def event_generator():
        """
        Generator function to yield events from the result stream.
        This allows for real-time updates to the client.
        """
        async for event in result.stream_events():
            if (event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent)):
                yield json.dumps({
                    "type": event.type,
                    "delta": event.data.delta
                }) + "\n"

            # elif (event.type == "run_item_stream_event"):
            #     if event.item.type == "tool_call_output_item":
            #         output = event.item.output

            #         yield json.dumps({
            #             "type": event.item.type,
            #             "tool_result": output
            #         }) + "\n"
            
    return StreamingResponse(
        event_generator(), media_type="application/json",
        headers={"Cache-Control": "no-cache"}
    )