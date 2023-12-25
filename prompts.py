filter_paper_prompt = """
You are an academic assistant that helps me to filter research papers that I may find interesting. 
I will give you a list of papers, including their index, title and abstract. You should select some papers from them based on my research interest. 
The maximum number of filtered papers is {num_filtered_papers}. You don't need to always select such many papers, but only choose those related to my interest. Less than 5 (even 0) papers are also acceptable.

Here are keywords describing my research interest:
{keywords}
{negative_keywords}
Your should not only consider papers whose title/abstract contain the above keywords, but also papers you think may be related to the above areas based on your knowledge.


Your output should be a list of indexes: 
[index1, index2, ...]
The indexes are **NOT** in the ascending order, but based on the **relevance and significance** of the papers. The most relevant paper should be the first index.
Please ensure that your output can be parsed by Python json.loads.



The cancidate papers are as follows:

{papers_info}

Please ensure that your output is a list of indexes following the order of relevance and significance and can be parsed by Python json.loads.
"""

email_title_template = "Daily papers {date} - Arxiv Assistant"

email_content_template = """
Look what I have found in today's arxiv papers that you may be interested!

{papers_info}
"""