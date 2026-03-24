# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv("/tmp/inputs/dotenv", override=True)

# Retrieve environment variables
OUTPUT_FOLDER = "/tmp/outputs"

HF_HOME = os.getenv("HF_HOME")
MODEL_NAME = os.getenv("MODEL_NAME")
HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE")

# Print the values (similar to echo in shell)
print(f"HF_HUB_OFFLINE: {HF_HUB_OFFLINE}")
print(f"HF_HOME: {HF_HOME}")
print(f"MODEL_NAME: {MODEL_NAME}")

sys.stdout.flush()

model_path = "/tmp/inputs/" + MODEL_NAME

import mteb

model = mteb.get_model(model_path)
model.mteb_model_meta.name = MODEL_NAME

def eval_task(model, task, split: str = "test", output_folder=OUTPUT_FOLDER):
    evaluation = mteb.MTEB(tasks=[task])
    results = evaluation.run(model, output_folder=f"{output_folder}", verbosity=0, eval_splits=[split])
    metric_sum = 0
    for score_on_split in results[0].scores[split]:
       metric_sum += score_on_split["main_score"]
    observed_value = metric_sum/len(results[0].scores[split])
    return observed_value

task_names = [
    "STS12",
    "STS13",
    "STS14",
    "STS15",
    "STS16",
    "STS17",
    "STS22.v2",
    "STSBenchmark",
    "DalajClassification.v2",
    "ScalaClassification",
    "SprintDuplicateQuestions",
    "MacedonianTweetSentimentClassification.v2",
    "StackExchangeClustering.v2",
    "TwitterURLCorpus",
    "PpcPC",
    "NusaParagraphEmotionClassification",
    "MultiHateClassification",
    "ToxicConversationsClassification",
    "BiorxivClusteringP2P.v2",
    "Tatoeba",
    "AmazonCounterfactualClassification",
    "ArXivHierarchicalClusteringS2S"
]

for task_name in task_names:
    print("Evaluating task: " + task_name)
    try:
        task = mteb.get_tasks(tasks=[task_name])[0]
        metric_name = task.metadata.main_score
        
        observed_metric_value = eval_task(model, task)

        output = {"task": task_name, "metric_name": metric_name,  "metric_value": observed_metric_value, "model_name": MODEL_NAME}
        print(json.dumps(output, indent=4))
        with open(f"{OUTPUT_FOLDER}/{task_name}_result.json", "w") as f:
            json.dump(output, f, indent=2)

    except Exception as exc:
        print("[ERROR] in " + task_name)
        print(exc)
        print("-"*20)

    print("-"*50)
    sys.stdout.flush()