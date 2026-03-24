This folder contains the proof-of-concept examples for certifying ML model properties, such as results of benchmarks or tests.

For HuggingFace repos, you may need an access token from HuggingFace (e.g., `hf_token`).
Please check the individual config files for where its path should be expected.

Note that the upload of the confidential assets, including the `hf_token`, happens
after the client remotely attests the controller and ensuring that it is running in a TEE.

Note also that for some HuggingFace repos, some Terms & Conditions need to be accepted
before it can be accessed using the `hf_token`.
Please do so via HuggingFace.

- [HuggingFaceTB/](HuggingFaceTB/): Model from HuggingFace repo HuggingFaceTB/SmolLM-135M
- [sentence-transformers/](sentence-transformers/): Model from HuggingFace repo sentence-transformers/all-MiniLM-L6-v2
- [sgugger/](sgugger/): Model from HuggingFace repo sgugger/glue-mrpc