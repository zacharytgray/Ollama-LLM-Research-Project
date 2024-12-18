import ast
import os
from colorama import Fore
import concurrent.futures
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv("/Users/zacharytgray/Documents/GitHub/Ollama-LLM-Sandbox/keys.env")
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key is None:
	print("API key for OpenAI not found.")
client = OpenAI(api_key=openai_api_key)

def main():

	numIterations = 4
	agent1 = Agent("Finn")
	agent2 = Agent("Jake")
	tasks = [("Task A", 6, 4), ("Task B", 8, 2), ("Task C", 9, 3), ("Task D", 7, 5)]
	domain = Domain(agent1, agent2, tasks)
	domain.assignTasks(numIterations)

	# agent1.printMemoryBuffer(otherAgent = agent2)
	# agent2.printMemoryBuffer(otherAgent = agent1)

def logMemoryBuffer(fileName, agent1, agent2):
		with open(fileName, "a") as f:
			f.write("Memory Buffer:\n")
			for dict in agent1.memoryBuffer:
				# if dict.get('role') == 'system':
				# 	f.write(f"System: {dict.get('content')}\n")
				if dict.get('role') == 'user':
					f.write(f"\n{agent2.name} (User): {dict.get('content')}\n")
				elif dict.get('role') == 'assistant':
					f.write(f"\n{agent1.name} (Assistant): {dict.get('content')}\n")

		f.close()

def logAssignedTasks(fileName, agent1, agent2):
	f = open(fileName, "a")
	f.write(f"\n{agent1.name}'s tasks: {agent1.assignedTasks}\n")
	f.write(f"{agent2.name}'s tasks: {agent2.assignedTasks}\n")
	f.close()

class Agent:
	def __init__(self, name) -> None:
		self.name = name
		self.assignedTasks = []
		self.numTokensGenerated = 0
		self.memoryBuffer = []
		self.model = 'gpt-4o-mini'
		self.temperature = 0.3
		self.instructionsFilename = "CollaborativeAllocators/CollaborativeSystemInstructions.txt"
		self.systemInstructions = f"Your name is {self.name}. "

		try:
			with open(self.instructionsFilename, "r") as f:
				self.systemInstructions += f.read()
			self.addToMemoryBuffer('system', self.systemInstructions)
		except FileNotFoundError:
			print(f"Error: {self.instructionsFilename} not found.")

		# Debugging: Print system instructions and memory buffer
		#print(f"System Instructions: {self.systemInstructions}")
		#print(f"Memory Buffer: {self.memoryBuffer}")

	def addToMemoryBuffer(self, role, inputText): #role is either 'user', 'assistant', or 'system'
		self.memoryBuffer.append({'role':role, 'content': inputText})

	def queryModel(self):
		def model_query():
			response = client.chat.completions.create(
			model=self.model,
			messages=self.memoryBuffer
			)
			self.numTokensGenerated += response.usage.total_tokens
			return response.choices[0].message.content

		with concurrent.futures.ThreadPoolExecutor() as executor:
			future = executor.submit(model_query)
			try:
				numMinutesTimeout = 5 # minutes
				return future.result(timeout = (60 * numMinutesTimeout))
			except concurrent.futures.TimeoutError:
				print(f"{Fore.RED}Error: Timeout in model query.{Fore.RESET}")
				return "TIMEOUTERROR"
	# def queryModel(self):
	# 	def model_query():
	# 		response = client.chat.completions.create(model=self.model,messages=self.memoryBuffer)
	# 		self.numTokensGenerated += response['usage']['total_tokens']
	# 		return response['choices'][0]['message']['content']

	# 	with concurrent.futures.ThreadPoolExecutor() as executor:
	# 		future = executor.submit(model_query)
	# 		try:
	# 			numMinutesTimeout = 5  # minutes
	# 			return future.result(timeout=(60 * numMinutesTimeout))
	# 		except concurrent.futures.TimeoutError:
	# 			print(f"{Fore.RED}Error: Timeout in model query.{Fore.RESET}")
	# 			return "TIMEOUTERROR"
		
	def run(self, role, inputText):
		self.addToMemoryBuffer(role, inputText)
		timeoutStr = "You took too long to respond. Please try again, avoiding any infinite loops."
      			
		withinTimeLimit = False
		hasResponse = False
		while not withinTimeLimit or not hasResponse:
			withinTimeLimit = False
			hasResponse = False
			response = self.queryModel()
   
			if response:
				hasResponse = True
			else:
				print(f"{Fore.RED}Error: No response from {self.name}.{Fore.RESET}")
    
			if response == "TIMEOUTERROR":
				if self.memoryBuffer[-1].get('content') != timeoutStr:
					print(f"{Fore.RED}Timeout: {self.name} took too long to respond. Trying again.{Fore.RESET}")
					self.addToMemoryBuffer('user', timeoutStr)
			else:
				withinTimeLimit = True
				self.addToMemoryBuffer('assistant', response)

		return response.strip()
	
	def printMemoryBuffer(self, otherAgent):
		print(f"\n{Fore.YELLOW}{self.name}'s Memory Buffer:{Fore.RESET}")
		for dict in self.memoryBuffer:
			if dict.get('role') == 'system':
				print(Fore.RED + "System: " + dict.get('content') + Fore.RESET)
			elif dict.get('role') == 'user':
				print(Fore.LIGHTBLUE_EX + f"{otherAgent.name} (User): " + dict.get('content') + Fore.RESET)
			elif dict.get('role') == 'assistant':
				print(Fore.LIGHTGREEN_EX + f"{self.name} (Assistant): " + dict.get('content') + Fore.RESET)
			else:
				print(f"{Fore.RED}Error: Invalid role in memory buffer: {dict.get('role')}")
				print(f"Content: {dict.get('content')}{Fore.RESET}")

	def addTask(self, task):
		if task not in self.assignedTasks:	
			self.assignedTasks.append(task)

	def numTasks(self):
		return len(self.assignedTasks)
	
class Domain:
	def __init__(self, agent1, agent2, tasks) -> None:
		self.consensusCounter = 0
		self.agent1 = agent1
		self.agent2 = agent2
		self.moderatorAgent = Agent("Moderator")
		self.tasks = tasks
		self.numConversationIterations = 0
		for task in self.tasks:
			taskDescription, PSR1, PSR2 = task
			agent1.systemInstructions +=  f"\n- {taskDescription}: Your PSR = {PSR1} out of 1.0."
			agent2.systemInstructions +=  f"\n- {taskDescription}: Your PSR = {PSR2} out of 1.0."
		
		agent1.systemInstructions += "\n\nLet's begin! Remember to be concise. Under no curcumstances should you accept an allocation with a lower Overall PSR than the highest one found, unless it causes one agent to have more tasks than the other."
		agent2.systemInstructions += "\n\nLet's begin! Remember to be concise. Under no curcumstances should you accept an allocation with a lower Overall PSR than the highest one found, unless it causes one agent to have more tasks than the other."
  
	def getConsensus(self):
		self.consensusCounter += 1
		self.agent1.assignedTasks = []
		self.agent2.assignedTasks = []
		self.moderatorAgent.memoryBuffer = []
		if self.consensusCounter > 3:
			self.moderatorAgent.systemInstructions = f"""
You have just received a conversation between {self.agent1.name} and {self.agent2.name}. You are the moderator for this task allocation conversation.
These two partners have been asked to allocate {len(self.tasks)} tasks between each other based on their own Probability of Success Rates (PSRs) for each task.
Rules:
- You are not going to change their decisions in any way. 
- Your job is to simply show me the results of their conversation in a dictionary format: {{'Task A':'AGENT NAME', 'Task B':'AGENT NAME', ...}}
- The allocation you should return is the one that yielded the highest Overall PSR from what they discussed.
- Note that 'AGENT NAME' is a placeholder for the name of the agent you think should be assigned that task based on their conversation. It should be replaced with '{self.agent1.name}' or '{self.agent2.name}'
- If they have not come to a consensus on a task, use your best judgement to select {self.agent1.name} or {self.agent2.name} for that task based on their conversation.
- Include apostrophes as shown around the task names and agent names to ensure the dictionary is formatted correctly.
- To ensure your message is a valid dictionary, make sure your response starts with an open curly bracket and ends with a curly bracket. 
- Do not inculde leading or trailing apostrophes. 
- Do not inclue any headers like 'python' or 'json'.
- Do not respond with any extra text, not even an introduction. Simply return the following, replacing 'AGENT NAME' as needed:

"""
		else:
			self.moderatorAgent.systemInstructions = f"""
You have just received a conversation between {self.agent1.name} and {self.agent2.name}. You are the moderator for this task allocation conversation.
These two partners have been asked to allocate {len(self.tasks)} tasks between each other based on their own Probability of Success Rates (PSRs) for each task.
Rules:
- You are not going to change their decisions in any way. 
- Your job is to simply show me the results of their conversation in a dictionary format: {{'Task A':'AGENT NAME', 'Task B':'AGENT NAME', ...}}
- The allocation you should return is the one that yielded the highest Overall PSR from what they discussed.
- Note that 'AGENT NAME' is a placeholder for the name of the agent you think should be assigned that task based on their conversation. It should be replaced with '{self.agent1.name}', '{self.agent2.name}', or 'TBD' if they have not come to a consensus on that task.
- Include apostrophes as shown around the task names and agent names to ensure the dictionary is formatted correctly.
- To ensure your message is a valid dictionary, make sure your response starts with an open curly bracket and ends with a curly bracket. 
- Do not inculde leading or trailing apostrophes. 
- Do not inclue any headers like 'python' or 'json'.
- Do not respond with any extra text, not even an introduction. Simply return the following, replacing 'AGENT NAME' as needed:

"""

		self.moderatorAgent.systemInstructions += "{"
		for task, _, _ in self.tasks:
			self.moderatorAgent.systemInstructions += f"'{task}':'AGENT NAME'," 
		self.moderatorAgent.systemInstructions = self.moderatorAgent.systemInstructions[:-1]
		self.moderatorAgent.systemInstructions += "}"
   
		memoryBuffer = self.agent1.memoryBuffer 
		for dialogue in memoryBuffer:
			if dialogue.get('role') == 'user':
				self.moderatorAgent.addToMemoryBuffer('user', f"{self.agent2.name}'s Response: " + dialogue.get('content'))
			elif dialogue.get('role') == 'assistant':
				self.moderatorAgent.addToMemoryBuffer('user', f"{self.agent1.name}'s Response: " + dialogue.get('content'))

		isDict = False
		notDictErrorStr = "You did not return a valid dictionary. Please follow the format precisely, with no additional text. A dictionary is formatted as {'key1':'value1', 'key2':'value2', ...}."
		while not isDict:
			rawConsensus = self.moderatorAgent.run('system', self.moderatorAgent.systemInstructions) # Should be {'task name':'agent name', ...}
			try:
				consensusDict = ast.literal_eval(rawConsensus)
				if not isinstance(consensusDict, dict):
					print("Error: rawConsensus is not a dictionary.")
				else:
					isDict = True
			except (ValueError, SyntaxError):
				print("Error: rawConsensus is not a valid Python dictionary.")	
			if not isDict:
				print("Raw consensus:\n	" + rawConsensus)
				self.moderatorAgent.addToMemoryBuffer('user', notDictErrorStr)

				
		disagreedTasks = "" # str of tasks that the agents disagreed on
		index = 0
		for task, agent in consensusDict.items():
			if not task or not agent:
				print(f"{Fore.RED}Error: Empty task or agent name in consensus: {task}, {agent}{Fore.RESET}")
				print(f"Raw Consensus: \n{rawConsensus}{Fore.RESET}")
				return False
			assignedTask = task.lower().strip()
			assignedAgent = agent.lower().strip()
   
			assignedTaskInTasks = False
			for task, PSR1, PSR2 in self.tasks: # Check if task name is valid
				if assignedTask == task.lower().strip():
					assignedTaskInTasks = True
					break
 
			if not assignedTaskInTasks:
				print(f"{Fore.RED}Error: Invalid task name in consensus: {assignedTask}{Fore.RESET}")
				print(f"Raw Consensus: \n{rawConsensus}{Fore.RESET}")
				return False
			
			if index < len(self.tasks):
				if assignedAgent == self.agent1.name.lower().strip():
					self.agent1.addTask(self.tasks[index])
				elif assignedAgent == self.agent2.name.lower().strip():
					self.agent2.addTask(self.tasks[index])
				elif assignedAgent == "tbd":
					print(f"No consensus reached for {assignedTask}")
					disagreedTasks += assignedTask + ", "
				else:
					print(f"{Fore.RED}Error: Invalid agent name in consensus: {assignedAgent} not equal to {self.agent1.name.lower().strip()} or {self.agent2.name.lower().strip()}{Fore.RESET}")
					print(f"Raw Consensus: \n{rawConsensus}{Fore.RESET}")
					return False
			index += 1

		if disagreedTasks != "":
			print(f"{Fore.RED}Disagreed on tasks: {disagreedTasks}{Fore.RESET}")
			print(f"Raw Consensus: \n{rawConsensus}{Fore.RESET}")
			self.agent1.addToMemoryBuffer('system', f"You did not come to complete agreement with {self.agent2.name} on task(s) {disagreedTasks[:-1]}. Please continue discussion to finalize the allocation. You must allocate all the tasks.")
			self.agent2.addToMemoryBuffer('system', f"You did not come to complete agreement with {self.agent1.name} on task(s) {disagreedTasks[:-1]}. Please continue discussion to finalize the allocation. You must allocate all the tasks.")
			return False

		if len(self.agent1.assignedTasks) + len(self.agent2.assignedTasks) > len(self.tasks):
			print(f"{Fore.RED}Error: Too many tasks assigned.")
			print(f"{self.agent1.name}'s tasks: {self.agent1.assignedTasks}")
			print(f"{self.agent2.name}'s tasks: {self.agent2.assignedTasks}{Fore.RESET}")
			return False
		elif len(self.agent1.assignedTasks) + len(self.agent2.assignedTasks) < len(self.tasks):
			print(f"{Fore.RED}Error: Not all tasks assigned.")
			print(f"{self.agent1.name}'s tasks: {self.agent1.assignedTasks}")
			print(f"{self.agent2.name}'s tasks: {self.agent2.assignedTasks}{Fore.RESET}")
			return False

		if len(self.agent1.assignedTasks) != len(self.agent2.assignedTasks):
			print(f"{Fore.RED}Error: Tasks not evenly split between agents.")
			print(f"{self.agent1.name}'s tasks: {self.agent1.assignedTasks}")
			print(f"{self.agent2.name}'s tasks: {self.agent2.assignedTasks}{Fore.RESET}")
   
			delta = abs(len(self.agent1.assignedTasks) - len(self.agent2.assignedTasks))
			if len(self.agent1.assignedTasks) > len(self.agent2.assignedTasks):
				self.agent1.addToMemoryBuffer("system", f"You and your partner did not split the tasks evenly. {self.agent1.name} was assigned {delta} more task(s) than {self.agent2.name}. Reevaluate your decisions conversationally until each of you has {len(self.tasks)/2} tasks assigned.")
				self.agent2.addToMemoryBuffer("system", f"You and your partner did not split the tasks evenly. {self.agent1.name} was assigned {delta} more task(s) than {self.agent2.name}. Reevaluate your decisions conversationally until each of you has {len(self.tasks)/2} tasks assigned.")
				return False
			else:
				self.agent1.addToMemoryBuffer("system", f"You and your partner did not split the tasks evenly. {self.agent2.name} was assigned {delta} more task(s) than {self.agent1.name}. Reevaluate your decisions conversationally until each of you has {len(self.tasks)/2} tasks assigned.")
				self.agent2.addToMemoryBuffer("system", f"You and your partner did not split the tasks evenly. {self.agent2.name} was assigned {delta} more task(s) than {self.agent1.name}. Reevaluate your decisions conversationally until each of you has {len(self.tasks)/2} tasks assigned.")
				return False
  
		return True


	def printTasks(self):
		print(f"\n{Fore.YELLOW}{self.agent1.name}'s tasks: {self.agent1.assignedTasks}")
		print(f"{self.agent2.name}'s tasks: {self.agent2.assignedTasks}{Fore.RESET}")
	

	def interruptConversation(self): #interrupt the conversation to allow the user to talk to agents directly
		#Type 1 to talk to agent 1
		#Type 2 to talk to agent 2
		#Type mb to see memory buffer
		#Type c to continue conversation

		userInput = ""
		while userInput.lower() != "c":
			userInput = input(f"\n{Fore.GREEN}What would you like to do? (1, 2, mb, c): {Fore.RESET}")
			if userInput != "c":
				if userInput == "1": #user wants to talk to agent 1
					userInput = input(f"Chat to Agent 1 ({self.agent1.name}): ")
					response = self.agent1.run("user", userInput)
					print(f"{self.agent1.name}: {response}")
				elif userInput == "2": #user wants to talk to agent 2
					userInput = input(f"Chat to Agent 2 ({self.agent2.name}): ")
					response = self.agent2.run("user", userInput)
					print(f"{self.agent2.name}: {response}")
				elif userInput == "mb": #user wants to see memory buffer
					self.agent1.printMemoryBuffer(self.agent2)
					self.agent2.printMemoryBuffer(self.agent1)
				else: 
					print("Pass...")

	def assignTasks(self, numIterations):
		self.agent1.addToMemoryBuffer('system', self.agent1.systemInstructions)
		self.agent2.addToMemoryBuffer('system', self.agent2.systemInstructions)
		
		currentInput = f"Hello! I'm {self.agent2.name}. Let's begin the task allocation. Please share your PSRs for each task."
		self.agent2.addToMemoryBuffer('assistant', currentInput)
	
		currentAgent = self.agent1
		consensusReached = False

		while not consensusReached:

			for i in range(numIterations):
				response = currentAgent.run("user", currentInput)
				if currentAgent == self.agent1:
					print(f"{Fore.LIGHTBLUE_EX}\n{currentAgent.name}: \n	{response}{Fore.RESET}")
				elif currentAgent == self.agent2:
					print(f"{Fore.LIGHTMAGENTA_EX}\n{currentAgent.name}: \n	{response}{Fore.RESET}")

				currentAgent = self.agent2 if currentAgent == self.agent1 else self.agent1
				currentInput = response
				self.numConversationIterations += 1

				if i == (numIterations-1): # Manually add final dialogue to agent 2
					self.agent2.addToMemoryBuffer('user', currentInput)

				# uncomment to allow user to talk to agents directly inbetween messages or see memory buffers live
				# self.interruptConversation() 
    
			print(f"\nAsking Moderator for Consensus...")
			consensusReached = self.getConsensus()
