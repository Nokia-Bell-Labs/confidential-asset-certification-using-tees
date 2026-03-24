# © 2026 Nokia
# Licensed under the BSD 3-Clause Clear License
# SPDX-License-Identifier: BSD-3-Clause-Clear

from dotenv import load_dotenv
import json
import sys

# Load environment variables from dotenv file
dotenv_path = "/tmp/inputs/dotenv"
load_dotenv(dotenv_path, override=True)

from datasets import load_dataset

import numpy as np

from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer

from evaluate import load

def preprocess_function(examples):
    return tokenizer(examples["sentence1"], examples["sentence2"], truncation=True)

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return metric.compute(predictions=predictions, references=labels)

def compute_model_card_evaluation_results(tokenizer, model_checkpoint, raw_datasets, metric):
    tokenized_datasets = raw_datasets.map(preprocess_function, batched=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_checkpoint, num_labels=2)
    batch_size = 16
    args = TrainingArguments(
        "test-glue",
        eval_strategy = "epoch",
        learning_rate=5e-5,
        seed=42,
        lr_scheduler_type="linear",
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        num_train_epochs=3,
        weight_decay=0.01,
        load_best_model_at_end=False,
        metric_for_best_model="accuracy",
        report_to="none"
        )

    trainer = Trainer(
        model,
        args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["validation"],
        tokenizer=tokenizer,
        compute_metrics=compute_metrics
    )
    result = trainer.evaluate()
    return result

if __name__ == "__main__":
    
    in_container = True
    if len(sys.argv) == 4:
        model_checkpoint = sys.argv[1]
        dataset_name = sys.argv[2]
        metric = sys.argv[3]
        in_container = False
    else:
        model_checkpoint = "sgugger/glue-mrpc"
        dataset_name = "nyu-mll/glue" 
        metric = ["glue", "mrpc"]
        in_container = True

    print(model_checkpoint, dataset_name, metric)

    raw_datasets = load_dataset(dataset_name, "mrpc")
    metric = load("/tmp/evaluate-metrics/metrics/glue/glue.py", "mrpc")

    tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)
    output = compute_model_card_evaluation_results(tokenizer, model_checkpoint, raw_datasets, metric)

    print(json.dumps(output, indent=4, sort_keys=True))
    if in_container:
        with open("/tmp/outputs/computation_result.json", "w") as f:
            json.dump(output, f, indent=4, sort_keys=True)
