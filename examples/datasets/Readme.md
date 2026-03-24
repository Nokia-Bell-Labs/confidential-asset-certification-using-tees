This folder contains the proof-of-concept examples for certifying dataset properties.
These examples include various modalities, such as text, code, images and audio, with various properties.

The folder also contains a library of common functions (i.e., [code/libprop/](code/libprop/)) that is useful for different modalities as well as a generic property computation code for tabular data (i.e., [code/tabular_info/](code/tabular_info/) that showcases a similar functionality as HuggingFace's Dataset Preview.

For HuggingFace repos, you may need an access token from HuggingFace (e.g., `hf_token`).
Please check the individual config files for where its path should be expected.

Note that the upload of the confidential assets, including the `hf_token`, happens
after the client remotely attests the controller and ensuring that it is running in a TEE.

Note also that for some HuggingFace repos, some Terms & Conditions need to be accepted
before it can be accessed using the `hf_token`.
Please do so via HuggingFace.

- [AquaV/](AquaV/): Dataset from HuggingFace AquaV/fallout-4-voices
- [bigcode/](bigcode/): Dataset from HuggingFace bigcode/the-stack-dedup
- [coco/](coco/): Datasets from COCO (Common Objects in Context)
- [code/libprop/](code/libprop/): Library of common functions for different modalities
- [code/tabular_info/](code/tabular_info/): Property computation code for tabular datasets
- [ILSVRC/](ILSVRC/): Dataset from ILSVRC/imagenet-1k 
- [Open-Orca/](Open-Orca/): Dataset from HuggingFace Open-Orca/OpenOrca
- [open-thoughts/](open-thoughts/): Dataset from HuggingFace open-thoughts/OpenThoughts-114k