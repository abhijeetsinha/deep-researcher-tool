import os
import time
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import DeepResearchTool, MessageRole

load_dotenv()

tenant_id = os.getenv('MS_TENANT_ID')
client_id = os.getenv('MS_CLIENT_ID')
client_secret = os.getenv('MS_CLIENT_SECRET')
email_sender = os.getenv('EMAIL_SENDER')

def get_token():
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        'client_id': client_id,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': client_secret,
        'grant_type': 'client_credentials'
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()['access_token']

def send_email(file_path):
    """Send email with research summary in body"""

    access_token = get_token()
    
    # Read file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Remove citation markers like 【70:3†source】
    content = re.sub(r'【\d+:\d+†source】', '', content)
    
    # Parse multiple recipients from comma-separated list
    recipients = [email.strip() for email in os.environ["EMAIL_RECIPIENT"].split(",")]
    
    # Create email
    email_data = {
        "message": {
            "subject": f"SASE Market News Summary - {datetime.now().strftime('%B %d, %Y')}",
            "body": {
                "contentType": "HTML",
                "content": content
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in recipients
            ]
        },
        "saveToSentItems": "true"
    }
    
    # Send via Microsoft Graph API
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    url = f"https://graph.microsoft.com/v1.0/users/{os.environ['EMAIL_SENDER']}/sendMail"
    response = requests.post(url, json=email_data, headers=headers)
    
    if response.status_code == 202:
        print(f"Email sent to {os.environ['EMAIL_RECIPIENT']}")
    else:
        print(f"Email failed: {response.status_code} - {response.text}")

def main():
    # Setup Azure AI Project
    project_client = AIProjectClient(
        endpoint=os.environ["PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )

    # Get Bing connection
    conn_id = project_client.connections.get(name=os.environ["BING_RESOURCE_NAME"]).id

    # Create Deep Research tool
    deep_research_tool = DeepResearchTool(
        bing_grounding_connection_id=conn_id,
        deep_research_model=os.environ["DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME"],
    )

    # Get agents client
    agents_client = project_client.agents
    
    # Create agent
    agent = agents_client.create_agent(
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
        name="cybersecurity-blog-summarizer",
        instructions="You are an AI agent that collects and summarizes cybersecurity blogs from key vendors every two weeks. Follow the steps below to identify, filter, and summarize articles.",
        tools=deep_research_tool.definitions,
    )
    print(f"Created agent: {agent.id}")

    # Create thread and send message
    thread = agents_client.threads.create()
    message = agents_client.messages.create(
            thread_id=thread.id,
            role="user",
            content=(
            """Summarize the blog articles published in the last two weeks from Zscaler, Palo Alto Networks, and Netskope. Below are the required steps and detailed process to collect, analyze, and summarize data.

# Steps

1. **Scope Identification**
   - Blogs from Zscaler, Palo Alto Networks, and Netskope are to be reviewed.
   - Review articles published only within the last two weeks from the following URLs:
     - Zscaler: https://www.zscaler.com/blogs
     - Zscaler product & insights: https://www.zscaler.com/blogs?type=product-insights
     - Zscaler news: https://www.zscaler.com/blogs?type=company-news
     - Zscaler press: https://www.zscaler.com/company/news-press
     - Palo Alto Networks: https://www.paloaltonetworks.com/blog/
     - Palo Alto Networks product & services: https://www.paloaltonetworks.com/blog/category/products-and-services/
     - Palo Alto Networks announcements: https://www.paloaltonetworks.com/blog/category/announcement/
     - Palo Alto Networks press: https://www.paloaltonetworks.com/company/press
     - Netskope: https://www.netskope.com/blog
     - Netskope Announcements: https://www.netskope.com/blog/category/netskope-announcements
     - Netskope Platform Products & Services: https://www.netskope.com/blog/category/platform-products-service
     - Netskope press: https://www.netskope.com/company/newsroom/press

2. **Analysis Approach**
   - Navigate through the blogs and filter by publication date (last two weeks).
   - Identify the key themes, insights, and products discussed.
   - Focus on the following aspects:
     - Product or service-related announcements.
     - Technological advancements or insights shared.
     - Industry trends or practices emphasized.
     - Key metrics or findings (if provided).

3. **Summarization Process**
   - Concisely summarize each article while ensuring clarity and accuracy.
   - Each summary should include:
     - Title of the article.
     - Publication date.
     - Key highlights and insights.
     - Original link of the article.

# Output Format

**IMPORTANT: Format the output as HTML for email rendering with proper styling and clickable links.**

**Do not include any headers like "Final Report", "Final report:", or similar prefixes. Start directly with the HTML content.**

Structure the HTML as follows:
- Use <h1> for main heading "SASE Market News Summary"
- Use <h2> for each vendor name (Zscaler, Palo Alto Networks, Netskope)
- Use <h3> for article titles (make them clickable links to original articles)
- Use <p> tags for dates and summaries
- Use <ul> and <li> for bullet points if needed
- Add spacing with <br> tags between articles
- Include a "References" section at the end with all source links

Example HTML structure:
```html
<h1>SASE Market News Summary</h1>
<p><em>Coverage Period: [Date Range]</em></p>

<h2>Zscaler</h2>
<h3><a href="[URL]">[Article Title]</a></h3>
<p><strong>Published:</strong> [Date]</p>
<p>[Summary text in 3-5 sentences]</p>
<br>

<h2>Palo Alto Networks</h2>
<h3><a href="[URL]">[Article Title]</a></h3>
<p><strong>Published:</strong> [Date]</p>
<p>[Summary text in 3-5 sentences]</p>
<br>

<h2>Netskope</h2>
<h3><a href="[URL]">[Article Title]</a></h3>
<p><strong>Published:</strong> [Date]</p>
<p>[Summary text in 3-5 sentences]</p>
<br>

<h2>References</h2>
<ul>
<li><a href="[URL]">[URL]</a></li>
</ul>
```

# Notes

- Output MUST be in HTML format for proper email rendering
- All article titles should be clickable hyperlinks to the original articles
- Summarizations should remain strictly accurate and neutral, reflecting the original blog content
- If blogs from certain URLs don't have any articles published in the last two weeks, exclude them from the results
- Ensure adherence to the timestamps for accuracy in capturing relevant information
"""
        ),
    )

    # Start agent run
    print("Starting research... this may take a few minutes.")
    run = agents_client.runs.create(thread_id=thread.id, agent_id=agent.id)
    
    # Wait for completion with progress updates
    last_msg_id = None
    while run.status in ("queued", "in_progress", "requires_action"):
        time.sleep(2)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
        
        # Show new responses
        messages = list(agents_client.messages.list(thread_id=thread.id))
        if messages and messages[0].role == "assistant" and messages[0].id != last_msg_id:
            msg = messages[0]
            for content in msg.content:
                if hasattr(content, 'text'):
                    print("\n" + content.text.value[:200] + "...")  # Show first 200 chars
            last_msg_id = msg.id
        
        print(f"Status: {run.status}")
    
    print(f"Run completed with status: {run.status}")

    # Save results
    print(f"\nFinished: {run.status}")
    if run.status == "failed":
        print(f"Error: {run.last_error}")
    else:
        messages = list(agents_client.messages.list(thread_id=thread.id))
        if messages and messages[0].role == "assistant":
            final = messages[0]
            # Combine all text content
            content = ""
            for content_item in final.content:
                if hasattr(content_item, 'text'):
                    content += content_item.text.value + "\n\n"
            
            # Remove citation markers
            content = re.sub(r'【\d+:\d+†source】', '', content)
            
            with open("research_summary.md", "w", encoding="utf-8") as f:
                f.write(content)
                # Add references if available
                annotations = []
                for content_item in final.content:
                    if hasattr(content_item, 'text') and hasattr(content_item.text, 'annotations'):
                        annotations.extend(content_item.text.annotations)
                
                if annotations:
                    f.write("\n\n<h2>References</h2>\n<ul>\n")
                    urls = set()
                    for ann in annotations:
                        if hasattr(ann, 'url_citation'):
                            urls.add(ann.url_citation.url)
                    for url in urls:
                        f.write(f"<li><a href=\"{url}\">{url}</a></li>\n")
                    f.write("</ul>\n")
            print("Saved to research_summary.md")
            
            # Send email with the summary
            send_email("research_summary.md")

    # Cleanup
    agents_client.delete_agent(agent.id)
    print("Done!")

if __name__ == "__main__":
    main()