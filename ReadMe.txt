brew install python3.10
python3.10 -m venv my_env                      
source /Users/ibilglobal/Projects/iLab/my_env/bin/activate
pip install instructlab
pip install llama-cpp-python
ilab config init
ilab model download
ilab model serve
ilab model chat
ilab data generate
ilab model train

ilab data generate --model models/merlinite-7b-lab-Q4_K_M.gguf --taxonomy-path qna.yaml --output-dir generated