import time
import json
import traceback
import warnings
import os
import math
from datetime import date, timedelta, datetime

import openai
import smtplib
import arxiv
from markdown2 import markdown
from email.mime.text import MIMEText
from email.header import Header

from prompts import filter_paper_prompt, email_title_template, email_content_template

class ArxivAssistant:
    def __init__(
            self, 
            mail_host,  #设置SMTP服务器，如smtp.qq.com
            mail_user,    #发送邮箱的用户名，如xxxxxx@qq.com
            mail_pass,  #发送邮箱的密码（注：QQ邮箱需要开启SMTP服务后在此填写授权码）
            
            categories, 
            keywords, 
            negative_keywords=None,
            
            mail_receivers=None,
            save_dir="./papers/",
            max_results_per_category=500,
            routine_interval_hours=6, # in hours
            
            gpt_filter=True,
            max_papers_per_query=50,
            num_filtered_papers=10,
            stream=False, response_max_tokens=512, temperature=0.7, 
            gpt_model="gpt-3.5-turbo-16k",
        ):
        
        self.mail_host = mail_host
        self.mail_user = mail_user
        self.mail_pass = mail_pass
        if mail_receivers is None:
            self.mail_receivers = [self.mail_user]
        else:
            self.mail_receivers = mail_receivers
        
        self.categories = categories
        self.keywords = keywords
        self.negative_keywords = negative_keywords
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)
        self.num_filtered_papers = num_filtered_papers
        self.max_results_per_category = max_results_per_category
        self.max_papers_per_query = max_papers_per_query
        self.routine_interval_hours = routine_interval_hours
        self.gpt_filter = gpt_filter
        
        self.stream = stream
        self.response_max_tokens = response_max_tokens
        self.temperature = temperature
        self.gpt_model = gpt_model
        
        self.run_dates = []
        self.today_str = date.today().strftime('%Y-%m-%d')
    
    def query_gpt_nostream(self, messages):
        server_error_cnt = 0
        if isinstance(messages, str):
            messages = [{"role": "user", "content" : messages}]
        while server_error_cnt < 3:
            try:
                response = openai.ChatCompletion.create(
                    model=self.gpt_model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.response_max_tokens,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    )
                response = response['choices'][0]['message']['content']
                return response
            except Exception as e:
                server_error_cnt += 1
                print(traceback.format_exc())
                time.sleep(pow(2, server_error_cnt))
        warnings.warn("Max number of trials exceeded for querying GPT")

    def query_gpt_stream(self, messages):
        server_error_cnt = 0
        if isinstance(messages, str):
            messages = [{"role": "user", "content" : messages}]
        full_response = ""
        while server_error_cnt < 3:
            try:
                for chunk in openai.ChatCompletion.create(
                    model=self.gpt_model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.response_max_tokens,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0, 
                    stream=self.stream,
                ):
                    content = chunk["choices"][0].get("delta", {}).get("content")
                    if content is not None:
                        print(content, end="", flush=True)
                        full_response += content
                print()
                full_response += "\n"
                return full_response
            except Exception as e:
                full_response = ""
                server_error_cnt += 1
                print(traceback.format_exc())
                time.sleep(pow(2, server_error_cnt))   
        warnings.warn("Max number of trials exceeded for querying GPT")

    def query_gpt(self, messages):
        if self.stream:
            return self.query_gpt_stream(messages)
        return self.query_gpt_nostream(messages)
    
    def send_mail_markdown(self, title, content, receiver, max_try=5):
        html_content = markdown(content)
        
        message = MIMEText(html_content, 'html', 'utf-8')
        message['From'] = self.mail_user
        message['To'] =  Header(receiver, 'utf-8') #收件人
        message['Subject'] = Header(title, 'utf-8')
        
        i = 0
        while i < max_try:
            try:
                smtpObj = smtplib.SMTP()
                smtpObj.connect(self.mail_host, 25)    # 25 为 SMTP 端口号
                smtpObj.login(self.mail_user, self.mail_pass)
                smtpObj.sendmail(self.mail_user, receiver, str(message))
                print("Email sent successfully")
                return 
            except smtplib.SMTPException as e:
                warnings.warn("ERROR with sending email: {e}")
                i += 1
        warnings.warn("Max number of trials exceeded for sending email")
    
    def fetch_yesterday_papers(self, max_try=5): 
        yesterday_date = None
        papers = {}
        for category in self.categories:
            papers[category] = []
            query = f'cat:{category}'
            search = arxiv.Search(
                query=query, 
                max_results=self.max_results_per_category, 
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            flag = False
            query_count = 0
            while query_count < max_try:
                try:
                    results = arxiv.Client().results(search)
                    for paper in results:
                        paper_date = paper.published.date()
                        if yesterday_date is None:
                            yesterday_date = paper_date
                            self.today_str = yesterday_date.strftime('%Y-%m-%d')
                            if self.today_str in self.run_dates:
                                # print(f"Not a new day {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                return []
                            
                        if paper_date == yesterday_date:
                            papers[category].append({
                                'title': paper.title,
                                'authors': [author.name for author in paper.authors],
                                'abstract': paper.summary.replace("\n", " "),
                                # 'date': paper.published.isoformat(),
                                'date': paper.published.strftime('%Y-%m-%d'),
                                'pdf_link': paper.pdf_url,
                                'abs_link': paper.entry_id,
                                'categories': paper.categories,
                            })
                        else:
                            break
                    print(f"Num of papers for {category} {self.today_str}: {len(papers[category])}")
                    flag = True
                    break
                except Exception as e:
                    # raise
                    print(f"Error with quering arxiv API: {e}")
                    query_count += 1
            if not flag:
                warnings.warn("Max number of trials exceeded for querying arxiv API")
                return []
                    

        
        with open(os.path.join(self.save_dir, f"{self.today_str}_all.json"), "w") as f:
            json.dump(papers, f, indent=4)
            
        papers_all = [p for v in papers.values() for p in v]
        return papers_all


    def gpt_filter_papers(self, input_papers, max_try=5):
        filtered_paper_indexes = []
        
        for i in range(math.ceil(len(input_papers) / self.max_papers_per_query)):
            temp_papers = input_papers[i * self.max_papers_per_query: (i + 1) * self.max_papers_per_query]
            prompt = self.format_prompt_input(temp_papers)
            # print(f"PROMPT:\n{prompt}\n\n")
            messages = [{"role": "user", "content": prompt}]
            
            flag = False
            query_count = 0
            while query_count < max_try:
                response = self.query_gpt(messages)
                try:
                    ret = json.loads(response)
                    assert isinstance(ret, list) and all(isinstance(item, int) for item in ret)
                    
                    filtered_paper_indexes.append([t - 1 + i * self.max_papers_per_query for t in ret])
                    flag = True
                    break
                except:
                    print(f"invalid response: {response}")
                    query_count += 1
            
            if not flag:
                warnings.warn("Max number of trials exceeded for querying GPT")
                return []
        
        # 希望得到一个列表b，其中的最开始几个元素是每个子列表的第一个元素，然后是每个子列表的第二个元素，……也就是类似于将列表a按行写为二维矩阵，然后再按列读取，但区别是每个子列表可能是不等长的
        # 找到最长子列表的长度
        max_len = max(len(sublist) for sublist in filtered_paper_indexes)
        # 初始化列表b
        filtered_paper_indexes_merged = []
        # 遍历每一列
        for i in range(max_len):
            for sublist in filtered_paper_indexes:
                if i < len(sublist):
                    filtered_paper_indexes_merged.append(sublist[i])
        
        filtered_papers = []
        removed_papers = []
        for idx, paper in enumerate(input_papers):
            if idx in filtered_paper_indexes_merged:
                filtered_papers.append(paper)
            else:
                removed_papers.append(paper)
        
        with open(os.path.join(self.save_dir, f"{self.today_str}_filtered.json"), "w") as f:
            json.dump(filtered_papers, f, indent=4)
        with open(os.path.join(self.save_dir, f"{self.today_str}_removed.json"), "w") as f:
            json.dump(removed_papers, f, indent=4)
        
        return filtered_papers
    
    
    def format_prompt_input(self, papers):
        papers_info = ""
        for idx, paper in enumerate(papers):
            papers_info += f"Index: {idx+1}\nTitle: {paper['title']}\nAbstract: {paper['abstract']}\n\n"
        if self.negative_keywords is None:
            negative_keywords = ""
        else:
            negative_keywords = f"\nI'm not interested in papers with the following keywords:\n{self.negative_keywords}\n"
        
        return filter_paper_prompt.format(
            num_filtered_papers=self.num_filtered_papers,
            keywords=self.keywords,
            negative_keywords=negative_keywords,
            papers_info=papers_info
        )
    
    
    def format_email(self, papers):
        papers_info = ""
        for idx, paper in enumerate(papers):
            single_paper_info = f"""{idx+1}. **{paper['title']}**
            
**Authors:** {', '.join(paper['authors'])}

**Abstract:** {paper['abstract']}

**Categories:** {', '.join(paper['categories'])}

PDF: {paper['pdf_link'].replace('v1', '')}

"""
            papers_info += single_paper_info
        title = email_title_template.format(date=date.today().strftime('%Y-%m-%d'))
        content = email_content_template.format(papers_info=papers_info)
        return title, content
        
        
    def run_routine(self):
        while True:
            papers = self.fetch_yesterday_papers()
            if len(papers) == 0:
                print(f"No new papers found {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(self.routine_interval_hours * 60 * 60)
                continue
            
            if self.gpt_filter:
                filtered_papers = self.gpt_filter_papers(papers)
                if len(filtered_papers) == 0:
                    print(f"No filtered papers {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    time.sleep(self.routine_interval_hours * 60 * 60)
                    continue
            else:
                filtered_papers = papers
            
            title, content = self.format_email(filtered_papers)
            for receiver in self.mail_receivers:
                self.send_mail_markdown(title, content, receiver)

            print(f"{len(filtered_papers)} papers filtered from {len(papers)} papers {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.run_dates.append(self.today_str)
            time.sleep(self.routine_interval_hours * 60 * 60)
            


if __name__ == '__main__':
    with open("openai_key.txt") as f:
        openai.api_key = f.read()
        
    with open("mail_info.json") as f:
        mail_info = json.load(f)
    
    assistant = ArxivAssistant(
        mail_host=mail_info["mail_host"],
        mail_user=mail_info["mail_user"],    #发送邮箱的用户名，如xxxxxx@qq.com
        mail_pass=mail_info["mail_pass"],  #发送邮箱的密码（注：QQ邮箱需要开启SMTP服务后在此填写授权码）
        
        categories=['cs.CV', 'cs.CL', 'cs.LG', 'cs.MA', 'cs.MM', 'cs.AI', 'cs.SD'], 
        keywords=['large language model', 'LLM', 'vision backbone', 'object detection', 'minecraft', 'agent', 'learning representation', 'multimodal',
                    'music generation', 'vision transformer', 'ViT'],
        negative_keywords=['3D', 'medical'],
        
        mail_receivers=mail_info.get("mail_receivers", None),
        # routine_interval_hours=0.0000001,
    )
    assistant.run_routine()
