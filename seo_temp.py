import csv
import concurrent.futures
import json
import os
import openai
import re
import random
import requests
import sys
import time
import io
import base64
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, TypedDict
from concurrent.futures import ThreadPoolExecutor, wait
from diffusers import StableDiffusionPipeline, EulerDiscreteScheduler

# Load .env file
load_dotenv()

# Get the API key
openai_api_key = os.getenv("OPENAI_API_KEY", "")
API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1-base"
headers = {"Authorization": f"Bearer {os.getenv('STABILITY_KEY')}"}

# Use the API key
openai.api_key = openai_api_key
openai.Model.list()

# load memory directory
memory_dir = os.getenv("MEMORY_DIRECTORY", "local")
workspace_path = "./"
if memory_dir == "production":
    workspace_path = "/tmp"
elif memory_dir == "local":
    workspace_path = "./"


class Message(TypedDict):
    role: str
    content: str

# ==================================================================================================
# API Interaction
# ==================================================================================================


def query(query_parameters: Dict[str, str]) -> bytes:
    try:
        response = requests.post(API_URL, headers=headers, json=query_parameters, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return b""


def stabilityai_generate(prompt: str,
                         size: str,
                         section: str) -> str:
    print(f"Generating {section} image...")
    image_bytes = query({
        "inputs": f"{prompt}",
        "size": size
    })
    byteImgIO = io.BytesIO(image_bytes)
    image = Image.open(byteImgIO)
    directory = Path(workspace_path) / 'content'
    os.makedirs(directory, exist_ok=True)
    image.save(directory / f'{section}.jpg')
    print("Done")
    return f'{section}.jpg'
    

def generate_content_response(prompt: str | List[Message],
                              temp: float,
                              p: float,
                              freq: float,
                              presence: float,
                              max_retries: int,
                              model: str) -> tuple:
    delay: float = 1  # initial delay
    exponential_base: float = 2
    jitter: bool = True
    num_retries: int = 0

    while True:
        if num_retries >= max_retries:
            print(f"Max retries exceeded. The API continues to respond with an error after " + str(
                max_retries) + " attempts.")
            return None, None, None, None  # return None if an exception was caught
        else:
            try:
                if isinstance(prompt, str):
                    response = openai.ChatCompletion.create(
                        model=f"{model}",
                        messages=[
                                {"role": "system", "content": "You are an web designer with the objective to identify search engine optimized long-tail keywords and generate contents, with the goal of generating website contents and enhance website's visibility, driving organic traffic, and improving online business performance."},
                                {"role": "user", "content": prompt}
                            ],
                        temperature=temp,
                        # max_tokens=2500,
                        top_p=p,
                        frequency_penalty=freq,
                        presence_penalty=presence,
                    )
                    # print (response)
                    return response.choices[0].message['content'], response['usage']['prompt_tokens'], response['usage']['completion_tokens'], response['usage']['total_tokens']
                elif isinstance(prompt, List):
                    # print("Prompt: ", prompt)
                    response = openai.ChatCompletion.create(
                        model=f"{model}",
                        messages=prompt,
                        temperature=temp,
                        # max_tokens=2500,
                        top_p=p,
                        frequency_penalty=freq,
                        presence_penalty=presence,
                    )
                    # print (response)
                    return response.choices[0].message['content'], response['usage']['prompt_tokens'], response['usage']['completion_tokens'], response['usage']['total_tokens']

            except openai.error.RateLimitError as e:  # rate limit error
                num_retries += 1
                print("Rate limit reached. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.Timeout as e:  # timeout error
                num_retries += 1
                print("Request timed out. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.ServiceUnavailableError:
                num_retries += 1
                print("Server Overloaded. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.InvalidRequestError as e:
                num_retries += 1
                print("Invalid Chat Request. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.APIConnectionError as e:
                #Handle connection error here
                print(f"Failed to connect to OpenAI API: {e}Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.APIError as e:
                num_retries += 1
                print(f"OpenAI API returned an API Error: {e}. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")

            # Increment the delay
            delay *= exponential_base * (1 + jitter * random.random())
            print(f"Wait for {round(delay, 2)} seconds.")

        time.sleep(delay)  # wait for n seconds before retrying


def generate_image_response(prompt: str,
                            max_retries: int) -> str:
    delay: float = 1  # initial delay
    exponential_base: float = 2
    jitter: bool = True
    num_retries: int = 0

    while True:
        if num_retries >= max_retries:
            print(f"Max retries exceeded. The API continues to respond with an error after " + str(
                max_retries) + " attempts.")
            return ""  # return "" if an exception was caught
        else:
            try:
                print("Generating image...")
                response = openai.Image.create(
                    prompt=prompt,
                    n=1,
                    size="1024x1024",
                )
                # print (response)
                return response['data'][0]['url']

            except openai.error.RateLimitError as e:  # rate limit error
                num_retries += 1
                print("Rate limit reached. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.Timeout as e:  # timeout error
                num_retries += 1
                print("Request timed out. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.ServiceUnavailableError:
                num_retries += 1
                print("Server Overloaded. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.InvalidRequestError as e:
                num_retries += 1
                print("Invalid Image Request. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
                # print("Prompt: ", prompt)
            except openai.error.APIConnectionError as e:
                num_retries += 1
                print(f"Failed to connect to OpenAI API: {e}Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
            except openai.error.APIError as e:
                num_retries += 1
                print(f"OpenAI API returned an API Error: {e}. Retry attempt " + str(num_retries) + " of " + str(max_retries) + "...")
                
            # Increment the delay
            delay *= exponential_base * (1 + jitter * random.random())
            print(f"Wait for {round(delay, 2)} seconds.")
            
            time.sleep(delay)  # wait for n seconds before retrying


def chat_with_gpt3(stage: str,
                   prompt: str | List[Message],
                   temp: float = 0.5,
                   p: float = 0.5,
                   freq: float = 0,
                   presence: float = 0,
                   model: str = "gpt-3.5-turbo") -> str:
    max_retries = 5       
    response, prompt_tokens, completion_tokens, total_tokens = generate_content_response(prompt, temp, p, freq, presence, max_retries, model)
    if response is not None:   # If a response was successfully received
        write_to_csv((stage, prompt_tokens, completion_tokens, total_tokens, None, None))
        return response
    else:
        return None


def chat_with_dall_e(prompt: str,
                     section: str) -> str:
    max_retries = 3
    url: str = generate_image_response(prompt, max_retries)
    if url is not None:   # If a response was successfully received
        return url
    else:
        return None

# =======================================================================================================================
# CSV Functions
# =======================================================================================================================


def write_to_csv(data: tuple):
    file_path = os.path.join(workspace_path, "token_usage.csv")
    file_exists = os.path.isfile(file_path)  # Check if file already exists
    with open(file_path, 'a+', newline='') as csvfile:
        fieldnames = ['Company Name', 'Keyword', 'Iteration', 'Stage', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens', 'Price']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()  # If file doesn't exist, write the header

        csvfile.seek(0)  # Move the file pointer to the beginning of the file so we can read from the start
        last_row = None
        for last_row in csv.DictReader(csvfile):
            pass  # The loop will leave 'last_row' as the last row
        if data[0] == 'Initial':
            iteration = 0
        else:
            iteration = int(last_row['Iteration']) + 1 if last_row else 0  # If there is a last row, increment its 'Iteration' value by 1. Otherwise, start at 0
        price = 0.000004 * data[3]  # Calculate the price of the request
        writer.writerow({'Company Name': data[4], 'Keyword': data[5], 'Iteration': iteration, 'Stage': data[0], 'Prompt Tokens': data[1], 'Completion Tokens': data[2], 'Total Tokens': data[3], 'Price': float(price)})

    # file_exists = os.path.isfile('token_usage.csv')  # Check if file already exists
    # with open('token_usage.csv', 'a', newline='') as csvfile:
    #     fieldnames = ['Company Name', 'Keyword', 'Iteration', 'Stage', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens', 'Price']
    #     writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    #     if not file_exists:
    #         writer.writeheader()
    #     writer.writerow({'Company Name': company_name, 'Keyword': topic, 'Iteration': 0, 'Stage': 'Initial', 'Prompt Tokens': 0, 'Completion Tokens': 0, 'Total Tokens': 0, 'Price': 0})

    
# ##==================================================================================================
# JSON Functions
# ##==================================================================================================

def deep_update(source, overrides):
    if not overrides or not isinstance(overrides, dict):
        return source
    for key, value in overrides.items():
        if isinstance(value, dict):
            # get node or create one
            node = source.setdefault(key, {})
            deep_update(node, value)
        else:
            source[key] = value
    return source


def update_json(data1):
    # convert the JSON strings to Python dictionaries:
    data2 = {
        "layouts": [
            {
                "layout": "Layout_header_1",
                "value": {
                    "image": "",
                    "position": 0
                }
            },
            {
                "layout": "Layout_centered_image_1",
                "value": {
                    "position": 1,
                    "button": [
                        {
                            "name": "",
                            "layout": 1
                        },
                        {
                            "name": "",
                            "layout": 2
                        }
                    ],
                    "image": "",
                    "h1": "",
                    "h2": ""
                }
            },
            {
                "layout": "Layout_right_image_1",
                "value": {
                    "position": 2,
                    "h2": "About Us",
                    "paragraph": "",
                    "image": ""
                }
            },
            {
                "layout": "Layout_three_blogs_1",
                "value": {
                    "position": 3,
                    "h2": "",
                    "blogs": [
                        {
                            "h2": "",
                            "paragraph": ""
                        },
                        {
                            "h2": "",
                            "paragraph": ""
                        },
                        {
                            "h2": "",
                            "paragraph": ""
                        }
                    ]
                }
            },
            {
                "layout": "Layout_contact_us_1",
                "value": {
                    "position": 4,
                    "h1": "Have a question?",
                    "h4": "Contact us today!",
                    "image": ""
                }
            },
            {
                "layout": "Layout_frequently_asked_questions_1",
                "value": {
                    "position": 5,
                    "h2": "Frequently Asked Questions",
                    "Faq": [
                        {
                            "h3": "",
                            "paragraph": ""
                        }
                    ]
                }
            },
            {
                "layout": "Layout_gallery_1",
                "value": {
                    "position": 6,
                    "images": [
                        {
                            "url": "",
                            "alt": ""
                        }
                    ]
                }
            },
            {
                "layout": "Layout_right_image_2",
                "value": {
                    "position": 7,
                    "h2": "",
                    "paragraph": "",
                    "image": ""
                }
            },
            {
                "layout": "Layout_map_1",
                "value": {
                    "position": 8,
                    "map_src": ""
                }
            },
            {
                "layout": "Layout_footer_1",
                "value": {
                    "position": 9,
                    "h1": "Contact Info",
                    "paragraph": ["", "", ""],
                    "image": ""
                }
            }
        ],
        "meta_data": {
            "title": "",
            "description": ""
        }
    }

    # update the second JSON data with the data from the first JSON:
    data2['layouts'][0]['value']['image'] = data1['logo']['image']
    
    data2['layouts'][1]['value']['h1'] = data1['banner']['h1']
    data2['layouts'][1]['value']['h2'] = data1['banner']['h2']
    data2['layouts'][1]['value']['button'] = data1['banner']['button']
    data2['layouts'][1]['value']['image'] = data1['banner']['image']

    data2['layouts'][2]['value']['h2'] = data1['about']['h2']
    data2['layouts'][2]['value']['paragraph'] = data1['about']['p']
    data2['layouts'][2]['value']['image'] = data1['about']['image']

    data2['layouts'][3]['value']['h2'] = data1['blogs']['h2']
    data2['layouts'][3]['value']['blogs'] = [{'h2': post['h3'], 'paragraph': post['p']} for post in data1['blogs']['post']]

    data2["layouts"][4]['value']['image'] = data1['contactus']['image']
    
    data2['layouts'][5]['value']['h2'] = data1['faq']['h2']
    data2['layouts'][5]['value']['Faq'] = [{'h3': q['h3'], 'paragraph': q['p']} for q in data1['faq']['question']]

    data2["layouts"][7]['value']['h2'] = data1['blog2']['h2']
    data2["layouts"][7]['value']['paragraph'] = data1['blog2']['p']
    data2["layouts"][7]['value']['image'] = data1['blog2']['image']
       
    data2['layouts'][6]['value']['images'] = [{'url': img, 'alt': ''} for img in data1['gallery']['image']]

    data2['layouts'][8]['value']['map_src'] = data1['map']['map_src']
    
    data2['layouts'][9]['value']['paragraph'] = data1['footer']['info']
    data2['layouts'][9]['value']['image'] = data1['logo']['image']
    
    data2['meta_data']['title'] = data1['meta']['title']
    data2['meta_data']['description'] = data1['meta']['description']
    # convert the updated data back to a JSON string:
    updated_json = json.dumps(data2)
    return data2


def processjson(jsonf: str) -> str:
    startindex = jsonf.find("{")
    endindex = jsonf.rfind("}")
    if startindex == -1 or endindex == -1:
        return ""
    else:
        try:
            json.loads(jsonf[startindex:endindex+1])
            return jsonf[startindex:endindex+1]
        except ValueError:
            return ""


def sanitize_filename(filename: str) -> str:
    """Remove special characters and replace spaces with underscores in a string to use as a filename."""
    return re.sub(r'[^A-Za-z0-9]+', '_', filename)


def sanitize_location(location: str) -> str:
    url_safe_address = location.replace(" ", "%20")
    url_safe_address = url_safe_address.replace(",", "%2C")
    return url_safe_address


def url_to_base64(url: str) -> str:
    try:
        response = requests.get(url)
        if response.status_code == 200:
            # Get the content of the response
            image_data = response.content

            # Convert the image data to a base64 string
            base64_image = base64.b64encode(image_data).decode('utf-8')
            return base64_image
        else:
            print("Unable to download image")
    except:
        return None

# def fail_safe(website: str) -> str:
#     if website.find('<!DOCTYPE html>') == -1:
#         website = htmlcode
#     return website


# ##===================================================================================================
# Content Generation Methods
# ##===================================================================================================


def get_industry(topic) -> str:
    prompt = f"Generate an industry for these keywords, no explanation is needed: {topic}"
    industry = chat_with_gpt3("Industry Identification", prompt, temp=0.2, p=0.1)
    print("Industry Found")
    return industry


def get_audience(topic: str) -> List[str]:
    audienceList = []
    prompt = f"Generate a list of target audience for these keywords, no explanation is needed: {topic}"
    audience = chat_with_gpt3("Target Search", prompt, temp=0.2, p=0.1)
    audiences = audience.split('\n')  # split the keywords into a list assuming they are comma-separated
    audiences = [target.replace('"', '') for target in audiences]
    audiences = [re.sub(r'^\d+\.\s*', '', target) for target in audiences]
    audienceList.extend(audiences)
    print("Target Audience Generated")
    return audienceList


def get_location(topic: str) -> str:
    print("Identifying Location..")
    prompt = f"Generate an address (Building number, Street name, Postal Code, City/Town name, State, Country) in one line for this keywords, no explanation is needed: {topic}"
    location = chat_with_gpt3("Location Identification", prompt, temp=0.2, p=0.1)
    print("Location Found")
    return location


def generate_long_tail_keywords(topic: str) -> List[str]:
    keyword_clusters = []
    prompt = f"Generate 5 SEO-optimized long-tail keywords related to the topic: {topic}."
    keywords_str = chat_with_gpt3("Keyword Clusters Search", prompt, temp=0.2, p=0.1)
    keywords = keywords_str.split('\n')  # split the keywords into a list assuming they are comma-separated
    keywords = [keyword.replace('"', '') for keyword in keywords]
    keywords = [re.sub(r'^\d+\.\s*', '', keyword) for keyword in keywords]
    keyword_clusters.extend(keywords)
    print("Keywords Generated")
    return keyword_clusters


def generate_title(company_name: str,
                   keyword: str) -> str:
    prompt = f"Suggest 1 SEO optimized headline about '{keyword}' for the company {company_name}"
    title = chat_with_gpt3("Title Generation", prompt, temp=0.7, p=0.8)
    title = title.replace('"', '')
    print("Titles Generated")
    return title


def generate_meta_description(company_name: str,
                              topic: str,
                              keywords: str) -> str:
    print("Generating meta description...")
    prompt = f"""
    Generate a meta description for a website based on this topic: '{topic}'.
    Use these keywords in the meta description: {keywords}
    """
    meta_description = chat_with_gpt3("Meta Description Generation", prompt, temp=0.7, p=0.8)
    return meta_description


def generate_footer(company_name: str, location: str):
    print("Generating footer")
    start = random.choice(["+601", "+603"])
    rest = "".join(random.choice("0123456789") for _ in range(8))  # we generate 8 more digits since we already have 2
    number = start + rest
    email = "info@" + company_name.lower().replace(" ", "") + ".com"
    address = location.replace("1. ", "", 1)
    url_location = sanitize_location(address)
    mapurl = f"https://maps.google.com/maps?q={url_location}&t=&z=10&ie=UTF8&iwloc=&output=embed"
    
    footer_json = {
        "map": {
            "map_src": ""
        },
        "footer": {
            "info": []
        }
    }
    footer_json['map']['map_src'] = mapurl
    footer_json['footer']['info'].extend([number, email, address])
    return footer_json


def generate_content(company_name: str,
                     topic: str,
                     industry: str,
                     keyword: str,
                     title: str) -> str:

    print("Generating Content...")
    directory_path = os.path.join(workspace_path, "content")
    os.makedirs(directory_path, exist_ok=True)
    json1 = """
    {
        "banner": {
                "h1": "...",
                "h2": "...",
                "button": [
                    {
                        "name": "...", 
                        "layout": 1
                    },
                    {
                        "name": "...",
                        "layout": 2
                    }...
                ] (Pick from these: Learn More, Contact Us, Get Started, Sign Up, Subscribe, Shop Now, Book Now, Get Offer, Get Quote, Get Pricing, Get Estimate, Browse Now, Try It Free, Join Now, Download Now, Get Demo, Request Demo, Request Quote, Request Appointment, Request Information, Start Free Trial, Sign Up For Free, Sign Up For Trial, Sign Up For Demo, Sign Up For Consultation, Sign Up For Quote, Sign Up For Appointment, Sign Up For Information, Sign Up For Trial, Sign Up For Demo, Sign Up For Consultation, Sign Up For Quote, Sign Up For Appointment, Sign Up For Information, Sign Up For Trial, Sign Up For Demo, Sign Up For Consultation, Sign Up For Quote, Sign Up For Appointment, Sign Up For Information, Sign Up For Trial, Sign Up For Demo, Sign Up For Consultation,  Sign Up For Quote, Sign Up For Appointment, Sign Up For Information)
        },
        "about": {
                "h2": "About Us",
                "p": "..."
        },
        "blogs":{
            "h2": "... (e.g.: Our Services, Customer Reviews, Insights, Resources)",
            "post": [{
                    "h3": "...",
                    "p": "...",
                },
                {
                    "h3": "...",
                    "p": "...",
                },
                {
                    "h3": "...",
                    "p": "...",
                }
            ]
        },
        "faq":{
            "h2": "Frequently Asked Questions",
            "question": [{
                    "id": 1,
                    "h3": "...",
                    "p": "...",
                },
                {
                    "id": 2,
                    "h3": "...",
                    "p": "...",
                },
                {
                    "id": 3,
                    "h3": "...",
                    "p": "...",
                },
                {
                    "id": 4,
                    "h3": "...",
                    "p": "...",
                },
                {
                    "id": 5,
                    "h3": "...",
                    "p": "...",
                },...
            ]
        },
        "blog2": {
                "h2": "Our Mission",
                "p": "..."
        }
    }
    """
    prompt = f"""
    Create a SEO optimized website content with the following specifications:
    Company Name: {company_name}
    Title: {title}
    Industry: {industry}
    Core Keywords: {topic}
    Keywords: {keyword}
    Format: {json1}
    Requirements:
    1) Make sure the content length is 700 words.
    2) The content should be engaging and unique.
    3) The FAQ section should follow the SERP and rich result guidelines
    """
    content = chat_with_gpt3("Content Generation", prompt, temp=0.7, p=0.8, model="gpt-3.5-turbo-16k")
    return content


def content_generation(company_name: str,
                       topic: str,
                       industry: str,
                       keyword: str,
                       title: str,
                       location: str) -> dict:
    try:
        description = generate_meta_description(company_name, topic, keyword)
        content = generate_content(company_name, topic, industry, keyword, title)
        footer = generate_footer(company_name, location)
    except Exception as e:
        return {'error': str(e)}
    content = processjson(content)
    contentjson = json.loads(content)
    updated_json = {"meta": {"title": title, "description": description}}
    updated_json.update(contentjson)
    updated_json.update(footer)
    print("Content Generated")
    # print(json.dumps(updated_json, indent=4))
    return updated_json


# =======================================================================================================================
# Image Generation
# =======================================================================================================================

def get_image_context(company_name: str,
                      keyword: str,
                      section: str,
                      topic: str,
                      industry: str) -> str:
    print("Generating Context...")
    examples = """
    Wide shot of a sleek and modern chair design that is currently trending on Artstation, sleek and modern design, artstation trending, highly detailed, beautiful setting in the background, art by wlop, greg rutkowski, thierry doizon, charlie bowater, alphonse mucha, golden hour lighting, ultra realistic./
    Close-up of a modern designer handbag with beautiful background, photorealistic, unreal engine, from Vogue Magazine./
    Vintage-inspired watch an elegant and timeless design with intricate details, and detailed lighting, trending on Artstation, unreal engine, smooth finish, looking towards the viewer./
    Close-up of modern designer a minimalist and contemporary lamp design, with clean lines and detailed lighting, trending on Artstation, detailed lighting, perfect for any contemporary space./
    Overhead view of a sleek and futuristic concept car with aerodynamic curves, and a glossy black finish driving on a winding road with mountains in the background, sleek and stylish design, highly detailed, ultra realistic, concept art, intricate textures, interstellar background, space travel, art by alphonse mucha, greg rutkowski, ross tran, leesha hannigan, ignacio fernandez rios, kai carpenter, perfect for any casual occasion./
    Close-up of a designer hand-crafting a sofa with intricate details, and detailed lighting, trending on Artstation, unreal engine, smooth finish./
    Low angle shot of a modern and sleek design with reflective lenses, worn by a model standing on a city street corner with tall buildings in the background, sleek and stylish design, highly detailed, ultra realistic./
    Saw and sawdust, blurred workshop background, 3D, digital art./
    Easy bake oven, fisher-price, toy, bright colors, blurred playroom background, natural-lighting./
    Fine acoustic guitar, side angle, natural lighting, bioluminescence./
    Tained glass window of fish, side angle, rubble, dramatic-lighting, light rays, digital art./
    Photo angles – a macro shot of the subject, or an overhead shot or a drone shot./
    Lighting – studio lighting, indoor lighting, outdoor lighting, backlit shots. /
    Photo lens effects – fisheye lens, double exposure /
    """
    prompt = f"""
    Generate 1 short paragraph about the detailed description of an image about {keyword}.
    The image should also be about {topic} 
    Use these as example descriptions: {examples}
    """

    prompt_messages: List[Message] = [
        {"role": "system",
         "content": "You are an web designer with the objective to identify search engine optimized long-tail keywords and generate contents, with the goal of generating website contents and enhance website's visibility, driving organic traffic, and improving online business performance."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about wood cutting carpentry workshop. The image should also be about carpentry workshop."},
        {"role": "assistant",
         "content": "Saw and sawdust, blurred workshop background, 3D, digital art."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about affordable toy oven for children. The image should also be about toy oven."},
        {"role": "assistant",
         "content": "Easy bake oven, fisher-price, toy, bright colors, blurred playroom background, natural-lighting."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about top acoustic guitar brands for professionals. The image should also be about acoustic guitar."},
        {"role": "assistant",
         "content": "Fine acoustic guitar, side angle, natural lighting, bioluminescence."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about Fish aquarium digital art gallery. The image should also be about fish aquarium digital art."},
        {"role": "assistant",
         "content": "Tained glass window of fish, side angle, rubble, dramatic-lighting, light rays, digital art."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about Contemporary ergonomic chair design. The image should also be about modern chair."},
        {"role": "assistant",
         "content": "Wide shot of a sleek and modern chair design that is currently trending on Artstation, sleek and modern design, artstation trending, highly detailed, beautiful setting in the background, art by wlop, greg rutkowski, thierry doizon, charlie bowater, alphonse mucha, golden hour lighting, ultra realistic."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about Trendy modern designer handbags for women. The image should also be about modern designer handbag."},
        {"role": "assistant",
         "content": "Close-up of a modern designer handbag with beautiful background, photorealistic, unreal engine, from Vogue Magazine."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about Luxury vintage-inspired and timeless watch. The image should also be about vintage-inspired timeless design watch."},
        {"role": "assistant",
         "content": "Vintage-inspired watch an elegant and timeless design with intricate details, and detailed lighting, trending on Artstation, unreal engine, smooth finish, looking towards the viewer."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about best modern designers lamp design. The image should also be about electrical lightings store."},
        {"role": "assistant",
         "content": "Close-up of modern designer a minimalist and contemporary lamp design, with clean lines and detailed lighting, trending on Artstation, detailed lighting, perfect for any contemporary space."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about award winning artistic design for a futuristic concept car. The image should also be about futuristic concept car."},
        {"role": "assistant",
         "content": "Overhead view of a sleek and futuristic concept car with aerodynamic curves, and a glossy black finish driving on a winding road with mountains in the background, sleek and stylish design, highly detailed, ultra realistic, concept art, intricate textures, interstellar background, space travel, art by alphonse mucha, greg rutkowski, ross tran, leesha hannigan, ignacio fernandez rios, kai carpenter, perfect for any casual occasion."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about finest hand-crafted quality sofa. The image should also be about sofa manufacturer."},
        {"role": "assistant",
         "content": "Close-up of a designer hand-crafting a sofa with intricate details, and detailed lighting, trending on Artstation, unreal engine, smooth finish."},
        {"role": "user",
         "content": "Generate 1 short paragraph about the detailed description of an image about Trendy designer sunglasses for summer. The image should also be about sunglasses."},
        {"role": "assistant",
         "content": "Low angle shot of a modern and sleek design with reflective lenses, worn by a model standing on a city street corner with tall buildings in the background, sleek and stylish design, highly detailed, ultra realistic."},
        {"role": "user",
         "content": f"Generate 1 short paragraph about the detailed description of an image about {keyword}. The image should also be about {topic} "}
    ]

    image_context = chat_with_gpt3("Image Description Generation", prompt_messages, temp=0.7, p=0.8)
    # print(image_context)
    imageurl = chat_with_dall_e(image_context, section)
    # print(imageurl)
    image_base64 = url_to_base64(imageurl)
    return image_base64


def generate_logo(company_name: str,
                  topic: str,
                  keyword: str,
                  industry: str,) -> str:
    print("Generating Logo")
    prompt = f"""
    Generate 1 logo concept for my {company_name} that incorporates sleek looking geometric shapes and modern sleek style, reflecting {topic} and {industry}. What color scheme would best complement this design?
    Write it in a few sentences
    """
    # A 2d, symmetrical, flat logo for a blockchain company that is sleek and simple. It should be of black shade and should be subtle.
    # Generate a sentence to describe the details and design of a logo for the company {company_name} that provides {topic}.
    logo_context = chat_with_gpt3("Logo Description Generation", prompt, temp=0.7, p=0.8)
    print(logo_context)
    imageurl = chat_with_dall_e(logo_context, "Logo")
    print(imageurl)
    image_base = url_to_base64(imageurl)
    return image_base
    
    
def generate_gallery_images(company_name: str,
                            keyword: str,
                            topic: str, 
                            industry: str) -> List[str]:
    gallery = []
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(get_image_context, company_name, keyword, f"gallery {i}", topic, industry): i for i in range(8)}

        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()  # Get the result of the future
                # result_base64 = url_to_base64(result)
                gallery.append(result)
            except Exception as e:
                print(f"An exception occurred during execution: {e}")
    return gallery


def image_generation(company_name: str,
                     topic: str,
                     industry: str,
                     keyword: str) -> Dict:
    print("Starting Image Process...")
    image_json = {
        "logo": {
            "image": ""
        },
        "banner": 
            {
                "image": ""
            },
        "about": 
            {
                "image": ""
            },
        "contactus":
            {
                "image": ""
            },
        "blog2":
            {
                "image": ""
            },
        "gallery": 
            {
                "image": []
            }
        
    }
    image_json["logo"]["image"] = generate_logo(company_name, topic, keyword, industry)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Start the threads and collect the futures for non-gallery sections
       
        futures = {executor.submit(get_image_context, company_name, keyword, section, topic, industry): section for section in ["banner", "about", "contactus", "blog2"]}

        # Add the gallery futures

        for future in concurrent.futures.as_completed(futures):
            section = futures[future]
            try:
                image_url: str = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (section, exc))
            else:
                if image_url:
                    image_json[section]["image"] = image_url
                    
    image_json["gallery"]["image"] = (generate_gallery_images(company_name, keyword, topic, industry))            
        
    print("Images Generated")
    return image_json


def feature_function(company_name: str,
                     topic: str,
                     industry: str,
                     selected_keyword: str,
                     title: str,
                     location: str) -> Dict:
    with concurrent.futures.ThreadPoolExecutor() as executor:
        image_future = executor.submit(image_generation, company_name, topic, industry, selected_keyword)
        content_future = executor.submit(content_generation, company_name, topic, industry, selected_keyword, title, location)
        futures = [image_future, content_future]
        done, not_done = concurrent.futures.wait(futures, timeout=60, return_when=concurrent.futures.ALL_COMPLETED)
        try:
            image_result = image_future.result()
            content_result = content_future.result()
        except Exception as e:
            print("An exception occurred during execution: ", e)

        if image_result is None or content_result is None:
            print("Error: No results returned")
            return {}
        else:
            merged_dict = deep_update(content_result, image_result)
            # print(json.dumps(merged_dict, indent=4))
            final_result = update_json(merged_dict)
            # print(json.dumps(final_result, indent=4))
            return final_result

# =======================================================================================================================
# Main Function
# =======================================================================================================================


def main():
    # Get the company name and topic from the user
    flag = True
    tries = 0
    max_tries = 2
    try:
        company_name = sys.argv[1]
        topic = sys.argv[2]
    except IndexError:
        company_name = input("Company Name: ")
        topic = input("Your Keywords: ")
    
    while flag:
        try:
            # Open token.csv to track token usage
            write_to_csv(("Initial", 0, 0, 0, company_name, topic))

            # Generate industry 
            industry = get_industry(topic)
            print(industry)
            
            location = get_location(topic)
            print(location)

            # Generate SEO keywords
            long_tail_keywords = generate_long_tail_keywords(topic)
            for number, keyword in enumerate(long_tail_keywords):
                print(f"{number+1}. {keyword}")

            # Generate title from keyword
            selected_keyword = long_tail_keywords[random.randint(0, 4)]
            print("Selected Keyword: " + selected_keyword)
            title = generate_title(company_name, selected_keyword)
            print(title)
            
            merged_dict = feature_function(company_name, topic, industry, selected_keyword, title, location)
            if merged_dict is None:
                print("Error: No results returned")
                if tries < max_tries:
                    tries += 1
                else:
                    print(f"Maximum tries exceeded. Exiting the program.")
                    flag = False
                    break
            else:
                flag = False
                # Write to JSON file
                directory_path = os.path.join(workspace_path, "content")
                os.makedirs(directory_path, exist_ok=True)
                with open(os.path.join(directory_path, f'data.json'), 'w', encoding='utf-8') as f:
                    json.dump(merged_dict, f, ensure_ascii=False, indent=4)
                
                # End procedures
                write_to_csv(("Complete", 0, 0, 0, company_name, topic))
                
        except Exception as e:
            tries += 1
            print(f"An exception occurred: {e}, retrying attempt {tries}")
            if tries <= max_tries:
                continue
            else:
                print(f"Maximum tries exceeded. Exiting the program.")
                break


if __name__ == "__main__":
    main()
