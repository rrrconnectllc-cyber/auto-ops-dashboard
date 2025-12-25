import os
import json
from openai import AsyncOpenAI

# Initialize the OpenAI Client
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

async def analyze_error(error_log: dict) -> dict:
    """
    Sends the error log to OpenAI (GPT-4o) and asks for a root cause & fix.
    """
    if not client.api_key:
        return {"error": "No OpenAI API Key found"}

    # The Prompt Engineering (The Secret Sauce)
    system_prompt = """
    You are a Senior Site Reliability Engineer (SRE) and Python Expert.
    Your job is to analyze infrastructure error logs.
    
    Output Format: return ONLY valid JSON with these keys:
    {
        "root_cause": "Brief explanation of what went wrong",
        "severity_score": 1-10,
        "suggested_fix_command": "The exact bash or python command to fix it",
        "risk_assessment": "Is this safe to run automatically? (Low/High)"
    }
    """

    user_message = f"""
    Here is the alert log I received:
    Source: {error_log.get('source')}
    Message: {error_log.get('message')}
    Metadata: {error_log.get('metadata')}
    
    Analyze this now.
    """

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",  # Or "gpt-3.5-turbo" if you want to save money while testing
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"} # This forces OpenAI to give us clean JSON
        )
        
        # Extract the answer
        content_text = response.choices[0].message.content
        
        return json.loads(content_text)
            
    except Exception as e:
        return {"error": str(e), "status": "Failed to analyze"}