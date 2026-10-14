import ollama

response = ollama.chat(
    model="llama3.2:3b",
    messages=[
        {
            "role": "user",
            "content": "Explain what an API is in two simple sentences."
        }
    ]
)

print(response["message"]["content"])
