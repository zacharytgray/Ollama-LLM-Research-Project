from colorama import Fore
from negotiationFlag import NegotiationFlag
from langchain.schema import AIMessage, HumanMessage, SystemMessage
import datetime
import random

class NegotiationManager:
    def __init__(self, negotiation):
        self.negotiation = negotiation
        self.deal_counter = 0
        self.agreement_reached = False

    def initialize_negotiation(self):
        negotiation_start_time = datetime.datetime.now().replace(microsecond=0)
        print(f"\n{Fore.GREEN}Round {self.negotiation.roundIndex} started{Fore.RESET}")
        
        starting_agent = self.select_starting_agent()
        current_agent, other_agent = self.get_agent_order(starting_agent)
        
        self.setup_initial_conditions()
        self.print_task_information()
        
        return negotiation_start_time, current_agent, other_agent

    def select_starting_agent(self):
        return random.choice([self.negotiation.agent1, self.negotiation.agent2])

    def get_agent_order(self, starting_agent):
        return ((self.negotiation.agent1, self.negotiation.agent2) 
                if starting_agent == self.negotiation.agent1 
                else (self.negotiation.agent2, self.negotiation.agent1))

    def setup_initial_conditions(self):
        self.negotiation.setUpInitialProposal()
        self.negotiation.proposalFormatExample = self.negotiation.setProposalFormattingExample(self.negotiation.agent1)
        self.negotiation.updateAgentInstructions()
        self.negotiation.agent1.addToChatHistory('system', self.negotiation.agent1.systemInstructions)
        self.negotiation.agent2.addToChatHistory('system', self.negotiation.agent2.systemInstructions)

    def print_task_information(self):
        print("Tasks for this negotiation:")
        for task in self.negotiation.tasks:
            print(f"{task.mappedName}: \n     {self.negotiation.agent1.agentName}: {task.confidence1}, \n     {self.negotiation.agent2.agentName}: {task.confidence2}")

    def process_proposal(self, current_agent, other_agent, current_input):
        max_retries = 5
        retries = 0
        
        while retries < max_retries:
            response = self.attempt_proposal(current_agent, current_input, retries)
            if response == NegotiationFlag.TIMEOUTERROR:
                retries = self.handle_timeout(retries, max_retries)
                continue

            proposal = self.negotiation.extractProposalFromReponse(response, current_agent)
            proposal_result = self.validate_proposal(proposal, current_agent)
            
            if proposal_result == NegotiationFlag.ERROR_FREE:
                return response, proposal
            
            retries += 1
            print(f"{Fore.RED}Invalid Proposal: {proposal_result}\n{current_agent.agentName}{response}{Fore.RESET}")
            print(f"{Fore.RED}Retrying... ({retries}/{max_retries} retries){Fore.RESET}")

        return None, None # Return None if retries exceed max_retries

    def attempt_proposal(self, current_agent, current_input, retries):
        if retries == 0:
            return current_agent.generateResponse(role='user', inputText=current_input)
        else:
            # Remove last 2 messages (the error response and the original input) if they exist
            if len(current_agent.memory) >= 3:
                current_agent.memory.pop(-1)  # Remove error response
                current_agent.memory.pop(-1)  # Remove original input for this iteration
            return current_agent.generateResponse() 
        
        #TODO: Currently testing the above code with removing agent responses from memory. Check if at this point the system instructions have been removed from memory, because if so, we might be removing an extra message.

    def handle_timeout(self, retries, max_retries):
        print(f"{Fore.RED}Response Timeout{Fore.RESET}")
        retries += 1
        print(f"{Fore.RED}Retrying... ({retries}/{max_retries} retries){Fore.RESET}")
        return retries

    def validate_proposal(self, proposal, current_agent):
        if isinstance(proposal, NegotiationFlag): 
            return self.handle_proposal_flag(proposal, current_agent) # Returns INVALID_PROPOSAL_FORMAT or PROPOSAL_NOT_FOUND
            
        if self.negotiation.numIterations == 0:
            return self.validate_initial_proposal(proposal, current_agent) # Returns ERROR_FREE or INVALID_PROPOSAL_FORMAT
            
        return proposal.validateProposal(self.negotiation.tasks)

    def handle_proposal_flag(self, flag, current_agent):
        if flag == NegotiationFlag.INVALID_PROPOSAL_FORMAT:
            self.negotiation.clearAllSystemMessages(current_agent)
            current_agent.addToChatHistory('system', self.get_format_error_message(current_agent))
        elif flag == NegotiationFlag.PROPOSAL_NOT_FOUND:
            self.negotiation.clearAllSystemMessages(current_agent)
            current_agent.addToChatHistory('system', self.negotiation.missingProposalWarning)
        elif flag == NegotiationFlag.INVALID_AGENT_NAME:
            self.negotiation.clearAllSystemMessages(current_agent)
            current_agent.addToChatHistory('system', self.negotiation.invalidJSONKeyWarning)
        return flag

    def validate_initial_proposal(self, proposal, current_agent):
        if self.negotiation.hasInitialProposal:
            if not self.negotiation.doesProposalMatchInitialProposal(proposal):
                helper_message = self.negotiation.setHelperMessage(current_agent)
                self.negotiation.clearAllSystemMessages(current_agent)
                current_agent.addToChatHistory('system', helper_message)
                return NegotiationFlag.INVALID_PROPOSAL_FORMAT
        elif proposal.hasDeal:
            self.negotiation.clearAllSystemMessages(current_agent)
            current_agent.addToChatHistory('system', "Initial proposal cannot be accepted")
            return NegotiationFlag.INVALID_PROPOSAL_FORMAT
        return NegotiationFlag.ERROR_FREE

    def get_format_error_message(self, current_agent):
        return f"""IMPORTANT: Remember to include the JSON object with the proposed tasks in your response.
                    Remember to include all tasks in your proposal. These are the tasks for this negotiation: {', '.join([task.mappedName for task in self.negotiation.tasks])} \n\nReformat your previous response to include the proposed tasks in the JSON format"""