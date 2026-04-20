# import google.generativeai as genai
# genai.configure(api_key="AIzaSyCM-7H5XBFDUBnAwOC6grlI2AiGqy4CZLo")
# for m in genai.list_models():
#     if "embedContent" in m.supported_generation_methods:
#         print(m.name)


from google import genai
client = genai.Client(api_key='AIzaSyCM-7H5XBFDUBnAwOC6grlI2AiGqy4CZLo')
result = client.models.embed_content(model='gemini-embedding-001', contents='test')
print('Dimensi:', len(result.embeddings[0].values))
