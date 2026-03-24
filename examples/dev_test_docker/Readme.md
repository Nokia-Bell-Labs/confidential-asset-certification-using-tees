## Development for Asset Certification

Here you can test your property computation code.
The `test_docker.py` script uses the same logic to build your container image from your code,
allowing you to save time and resources while developing and testing it.
Afterwards, you can use the same code for certification purposes.

First, install the requirements.

```
python3 -m pip install -r requirements.txt
```

Then, you can give your example config file:

```
python3 test_docker.py <example_config.json>
```

After your property computation code runs in a container, the output files of your will be available in `test_temp/tmp/outputs/` folder.

### Note for HuggingFace models and datasets

Some HuggingFace models and datasets may require acceptance of terms and conditions.
To do so,
1) log in to the website, 
2) accept the terms of the model/dataset in question, 
3) obtain your token for API access from huggingface settings,
4) store your token in a path (e.g., ./) accessible to your config file
5) refer to the token path in your certification config file that you are testing.

Using this token, the script will access various model/dataset files and download them locally, 
in order to be able to test the piece of property computation code you are developing.
