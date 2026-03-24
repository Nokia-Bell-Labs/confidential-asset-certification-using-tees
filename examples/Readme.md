# Asset Certification Examples

This repo contains the codebase for the property computations for various types of assets (e.g., datasets, models, software) and the corresponding [third-party verifiable](../asset_certification_client/asset_certificate_verifier.py) certificates. It also contains the tools for developing and testing property computation code in an emulator-like environment: the property computation is tested in a docker container with the same environment and necessary inputs as it would be launched in the [Asset Certification Service with duet](../).

These examples solely exist as a proof-of-concept; that's why they use already open-sourced assets.
This may not always be the case.
Furthermore, in some scenarios, the users of the assets may not always have the resources to validate whether an asset satisfies their needs (i.e., by downloading the entire asset and checking its content).

## Repo Structure

- [certificates/](certificates/): The certificates that were created using the [Asset Certification Service with duet](../) for the respective assets.

- [datasets/](datasets/): The property computation code and configuration files for dataset assets.

- [dev_test_docker/](dev_test_docker/): The tools that emulate the certification service environment to develop and test a new property computation code.

- [models/](models/): The property computation code and configuration files for model assets.

- [software/](software/): The property computation code and configuration files for software assets.
