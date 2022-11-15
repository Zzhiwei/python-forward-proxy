import requests

proxies = {
   'http': 'http://localhost:8080',
}

# url = 'http://local'

# while True:
  # url = input('enter a website:')
url = 'http://localhost:3000'
response = requests.get(url, proxies=proxies)
print(response.json())
# print(response.raw())
# print(response.json())
# print('\n')
# print(response.raw())
