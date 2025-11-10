import os
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import DeepResearchTool, MessageRole

load_dotenv()

def send_email(file_path):
    """Send email with research summary in body"""
    # Read file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Create email
    email_data = {
        "message": {
            "subject": f"SASE Market News Summary - {datetime.now().strftime('%B %d, %Y')}",
            "body": {
                "contentType": "Text",
                "content": content
            },
            "toRecipients": [
                {"emailAddress": {"address": os.environ["EMAIL_RECIPIENT"]}}
            ]
        },
        "saveToSentItems": "true"
    }
    
    # Send via Microsoft Graph API
    headers = {
        "Authorization": f"Bearer {os.environ['EMAIL_BEARER_TOKEN']}",
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

    with project_client.agents as agents_client:
        
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
        agents_client.messages.create(
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
     - Palo Alto Networks: https://www.paloaltonetworks.com/blog/
     - Palo Alto Networks product & services: https://www.paloaltonetworks.com/blog/category/products-and-services/
     - Palo Alto Networks announcements: https://www.paloaltonetworks.com/blog/category/announcement/
     - Netskope: https://www.netskope.com/blog
     - Netskope Announcements: https://www.netskope.com/blog/category/netskope-announcements
     - Netskope Platform Products & Services: https://www.netskope.com/blog/category/platform-products-service

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

Summarized data should be presented in JSON format as follows:

[
  {
    "source": "Zscaler",
    "title": "[Article Title]",
    "publication_date": "[Date]",
    "summary": "[Key highlights of the article in 3-5 sentences]",
    "Original article link": "[article hyperlink]"
  },
  {
    "source": "Palo Alto Networks",
    "title": "[Article Title]",
    "publication_date": "[Date]",
    "summary": "[Key highlights of the article in 3-5 sentences]",
    "Original article link": "[article hyperlink]"
  },
  {
    "source": "Netskope",
    "title": "[Article Title]",
    "publication_date": "[Date]",
    "summary": "[Key highlights of the article in 3-5 sentences]",
    "Original article link": "[article hyperlink]"
  }
]

# Examples

### Example 1: Summary Output for Zscaler

{
  "source": "Zscaler",
  "title": "Enhancing Cloud Security with Zero Trust Innovations",
  "publication_date": "2023-10-01",
  "summary": "This article delves into Zscaler's latest advancements in zero trust security for cloud environments. It emphasizes the importance of greater visibility across multicloud platforms and introduces a new model for user access control tailored for hybrid workforces. The blog also highlights their newest integration capabilities to simplify deployments.",
  "Original article link": "www.example.com"
}

### Example 2: Summary Output for Palo Alto Networks

{
  "source": "Palo Alto Networks",
  "title": "The Role of AI in Improving SASE Effectiveness",
  "publication_date": "2023-10-02",
  "summary": "The blog outlines how AI is transforming SASE solutions by enhancing risk mitigation and automation capabilities. Palo Alto Networks discusses the introduction of predictive threat detection tools powered by AI algorithms to address vulnerabilities proactively. The post further highlights customer success stories and measurable reductions in incident response times.",
  "Original article link": "www.example.com"
}

# Notes

- Summarizations should remain strictly accurate and neutral, reflecting the original blog content. Avoid interpretation unless explicitly stated in the blog.
- If blogs from certain URLs don't have any articles published in the last two weeks, exclude them from the results.
- Ensure adherence to the timestamps for accuracy in capturing relevant information."""
        ),
        )

        # Start agent run
        print("Starting research... this may take a few minutes.")
        run = agents_client.runs.create(thread_id=thread.id, agent_id=agent.id)
        
        # Wait for completion
        last_msg_id = None
        while run.status in ("queued", "in_progress"):
            time.sleep(1)
            run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
            
            # Show new responses
            response = agents_client.messages.get_last_message_by_role(
                thread_id=thread.id, role=MessageRole.AGENT
            )
            if response and response.id != last_msg_id:
                print("\n" + "\n".join(t.text.value for t in response.text_messages))
                for ann in response.url_citation_annotations:
                    print(f"[{ann.url_citation.title}]({ann.url_citation.url})")
                last_msg_id = response.id
            
            print(f"Status: {run.status}")

        # Save results
        print(f"\nFinished: {run.status}")
        if run.status == "failed":
            print(f"Error: {run.last_error}")
        else:
            final = agents_client.messages.get_last_message_by_role(
                thread_id=thread.id, role=MessageRole.AGENT
            )
            if final:
                with open("research_summary.md", "w", encoding="utf-8") as f:
                    f.write("\n\n".join(t.text.value for t in final.text_messages))
                    if final.url_citation_annotations:
                        f.write("\n\n## References\n")
                        for ann in set(a.url_citation.url for a in final.url_citation_annotations):
                            f.write(f"- {ann}\n")
                print("Saved to research_summary.md")
                
                # Send email with the summary
                send_email("research_summary.md")

        # Cleanup
        agents_client.delete_agent(agent.id)
        print("Done!")

if __name__ == "__main__":
    main()