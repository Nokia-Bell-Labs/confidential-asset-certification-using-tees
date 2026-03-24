Contributed by: Janwillem Swalens

Integrated and tested by: Istemi Ekin Akkus

This folder contains the property computation code for [HuggingFace Open-Orca/OpenOrca](https://huggingface.co/datasets/Open-Orca/OpenOrca) dataset.

## Properties extracted:
- For the column "system_prompt":
    - cell_unique_count: the unique count
    - cell_count_per_unique: the unique values and their counts

## Example output of the custom properties for the "system_prompt" column (on 1M-GPT4-Augmented):
```json
    "cell_unique_count": 17,
    "cell_count_per_unique": {
        "": 75897,
        "Explain how you used the definition to come up with the answer.": 9720,
        "Given a definition of a task and a sample input, break the definition into small parts.\nEach of those parts will have some instruction. Explain their meaning by showing an example that meets the criteria in the instruction. Use the following format:\nPart  # : a key part of the definition.\nUsage: Sample response that meets the criteria from the key part. Explain why you think it meets the criteria.": 10100,
        "User will you give you a task with some instruction. Your job is follow the instructions as faithfully as you can. While answering think step-by-step and justify your answer.": 9954,
        "You are a helpful assistant, who always provide explanation. Think like you are answering to a five year old.": 158260,
        "You are a teacher. Given a task, you explain in simple steps what the task is asking, any guidelines it provides and how to use those guidelines to find the answer.": 9834,
        "You are an AI assistant that follows instruction extremely well. Help as much as you can.": 75909,
        "You are an AI assistant that helps people find information.": 24716,
        "You are an AI assistant that helps people find information. Provide a detailed answer so user don\u2019t need to search outside to understand the answer.": 24746,
        "You are an AI assistant that helps people find information. User will you give you a question. Your task is to answer as faithfully as you can. While answering think step-bystep and justify your answer.": 24710,
        "You are an AI assistant, who knows every language and how to translate one language to another. Given a task, you explain in simple steps what the task is asking, any guidelines that it provides. You solve the task and show how you used the guidelines to solve the task.": 9706,
        "You are an AI assistant. Provide a detailed answer so user don't need to search outside to understand the answer.": 78,
        "You are an AI assistant. Provide a detailed answer so user don\u2019t need to search outside to understand the answer.": 76293,
        "You are an AI assistant. User will you give you a task. Your goal is to complete the task as faithfully as you can. While performing the task think step-by-step and justify your steps.": 234334,
        "You are an AI assistant. You should describe the task and explain your answer. While answering a multiple choice question, first output the correct answer(s). Then explain why other answers are wrong. You might need to use additional knowledge to answer the question.": 13301,
        "You are an AI assistant. You will be given a task. You must generate a detailed and long answer.": 224109,
        "You should describe the task and explain your answer. While answering a multiple choice question, first output the correct answer(s). Then explain why other answers are wrong. Think like you are answering to a five year old.": 13229
    },
```