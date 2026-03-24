
- `eval.py` is the script that needs to be run by the certification service. It loads in a given model and uses a predefined list of tasks/benchmarks on which it will evaluate the model and produce a .json file with the evaluation results. The file assumes that the following data is in /tmp/inputs:
    - a `.env` file (e.g., see `contributions/code_models/all-MiniLM-L6-v2/.env`)
    - an embedding model (e.g., `/tmp/inputs/sentence-transformers/all-MiniLM-L6-v2`)
- `reproducability_tests.ipynb` checks for which tasks we can reproduce (✅) the leaderboard results for the smaller tasks from https://huggingface.co/spaces/mteb/leaderboard. 
We can't exactly reproduce the results for all benchmark.
    - AILAStatutes ✅
    - SprintDuplicateQuestions ✅
    - TwitterURLCorpus ✅
    - PpcPC ✅
    - STS12 ✅
    - STS13 ✅
    - STS14 ✅
    - STS15 ✅
    - STS16 ✅
    - STS17 ✅
    - STS22.v2 ✅
    - STSBenchmark ✅
    - DalajClassification ✅
    - MassiveIntentClassification ❌ (observed: 27.85, reported: 27.58)
    - MedrxivClusteringP2P.v2 ❌ (observed: 37.49, reported: 37.61)
    - ScalaClassification ✅ (very slight difference; observed: 50.2954, reported: 50.29419)
    - AmazonCounterfactualClassification ❌ (observed: 61.99, expected_value: 61.28)
    - MacedonianTweetSentimentClassification ✅
    - MultiHateClassification ✅
    - NusaParagraphEmotionClassification ✅
    - ToxicConversationsClassification ✅
    - ArXivHierarchicalClusteringS2S ❌ (observed: 54.58, reported: 54.54)
    - ArguAna ✅ (slight difference; observed: 50.169, reported: 50.167)
    - BiorxivClusteringP2P.v2 ✅
    - StackExchangeClustering.v2 ❌❌ (observed: 51.805, reported: 45.168)
    - Tatoeba ✅

The eval.py script only uses the reproducable ✅ tasks.
