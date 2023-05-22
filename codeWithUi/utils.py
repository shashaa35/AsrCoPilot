import openai
import streamlit as st
# given a vm arm id, fetch the details from azure
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient
from contexts import *
from langchain.llms import AzureOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.document_loaders import UnstructuredMarkdownLoader

azure_credential = ClientSecretCredential(
        client_id="7d595cf7-3da6-4f46-8f37-8d7ba50c520c",
        client_secret=st.secrets["azure_service_principle_key"],
        tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47"
        )

key = st.secrets["azure_openai_key"]
openai.api_type = "azure"
openai.api_base = "https://asr-test-env.openai.azure.com/"
openai.api_version = "2023-03-15-preview"
openai.api_key = key

def get_initial_message():
    if st.session_state['current_feature'] == "pricing":
        system_input = system_input_pricing
        vm_details = st.session_state['vm_details']
    messages=[
            {"role": "system", "content": system_input},
            {"role": "user", "content": "I want to know the pricing for the vm with details in triple backticks below : ```" + str(vm_details) + "```. Provide the response in tabular format with one row for each vm with each component as column."},
        ]
    return messages

def clear_cache():
    if 'messages' in st.session_state:
        del st.session_state['messages']
    if 'first_response' in st.session_state:
        del st.session_state['first_response']
    if 'vm_details' in st.session_state:
        del st.session_state['vm_details']
    if 'generated' in st.session_state:
        del st.session_state['generated']
    if 'past' in st.session_state:
        del st.session_state['past']

def get_chatgpt_response(messages, model="gpt-3.5-turbo"):
    if 'calls_to_gpt' not in st.session_state:
        st.session_state['calls_to_gpt'] = 0
    print("Call : ", st.session_state['calls_to_gpt'] + 1)
    print(messages)
    print("-----------------------------------------------")
    response = openai.ChatCompletion.create(
        engine="testDeployment-Nilesh",
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=1000,
    )
    st.session_state['calls_to_gpt'] += 1
    return  response['choices'][0]['message']['content']

def update_chat(messages, role, content):
    messages.append({"role": role, "content": content})
    return messages

def set_faq_context():
    if 'chain' not in st.session_state:
        embeddings = OpenAIEmbeddings(
            openai_api_key=key,
            openai_api_base='https://asr-test-env.openai.azure.com/',
            deployment="shashankTextSearch")
        data = load_and_return_md_document("A2A_Architecture.md")
        #print(data[0].page_content)
        db = Chroma.from_documents(data, embeddings)
        retriever = db.as_retriever(search_type='similarity', search_kwargs={'k':1})
        chain = RetrievalQAWithSourcesChain.from_chain_type(
            AzureOpenAI(
            openai_api_key=key,
            openai_api_base='https://asr-test-env.openai.azure.com/',
            deployment_name="testDeployment-Nilesh",
            temperature=0,
            max_tokens=500),
            chain_type="stuff",
            retriever=retriever,
            max_tokens_limit = 1000
            )
        st.session_state['chain'] = chain

def answerQuestion(question):
    q = faq_prompt.format(question=question) 
    if 'chain' not in st.session_state:
        set_faq_context()
    chain = st.session_state['chain']
    response = chain({"question": q}, return_only_outputs=True)
    print(response)
    print(q)
    print("-----------------------------------------------")
    return response['answer']

def load_and_return_md_document(doc = "A2A_Architecture.md"):
    markdown_path = "./" + doc
    loader = UnstructuredMarkdownLoader(markdown_path)
    data = loader.load()
    return data


@st.cache_data
def get_vm_details(vm_arm_id):
    vm_arm_id_arr = vm_arm_id.split('/')
    # Extract the subscription ID, resource group, and VM name from the ARM ID
    subscription_id, resource_group, vm_name = vm_arm_id_arr[2], vm_arm_id_arr[4], vm_arm_id_arr[8]
    st.write(subscription_id, resource_group, vm_name)
    # Create a ComputeManagementClient instance
    compute_client = ComputeManagementClient(azure_credential, subscription_id)

    # Fetch the VM details using the ARM ID
    vm = compute_client.virtual_machines.get(resource_group, vm_name)

    # Access specific details
    vm_name = vm.name
    vm_location = vm.location
    vm_size = vm.hardware_profile.vm_size
    disks = []
    disks.append({
        'disk_type': 'OS',
        'disk_name': vm.storage_profile.os_disk.name,
        'disk_size': str(vm.storage_profile.os_disk.disk_size_gb),
        'disk_sku': vm.storage_profile.os_disk.managed_disk.storage_account_type
    })
    for data_disk in vm.storage_profile.data_disks:
        disks.append({
            'disk_type': 'Data',
            'disk_name': data_disk.name,
            'disk_size': str(data_disk.disk_size_gb),
            'disk_sku': data_disk.managed_disk.storage_account_type
        })
    # Return the fetched details as a dictionary
    vm_details = {
        'VM Name': vm_name,
        'Location': vm_location,
        'VM Size': vm_size,
        'OS Type': vm.storage_profile.os_disk.os_type,
        'disks': disks
    }
    return vm_details

# get_vm_details for multiple vm_arm_ids that are passed as comma separated string
@st.cache_data
def get_vm_details_multiple(vm_arm_ids):
    vm_arm_ids_arr = vm_arm_ids.split(',')
    vm_details = []
    for vm_arm_id in vm_arm_ids_arr:
        vm_details.append(get_vm_details(vm_arm_id))
    return vm_details

# get_vm_details for all vms in a resource group
@st.cache_data
def get_vm_details_rg(resource_group_arm_id):
    resource_group_arm_id_arr = resource_group_arm_id.split('/')
    # Extract the subscription ID and resource group from the ARM ID
    subscription_id, resource_group = resource_group_arm_id_arr[2], resource_group_arm_id_arr[4]
    st.write("Fetching details for resource group : "+ resource_group)
    # Create a ComputeManagementClient instance
    compute_client = ComputeManagementClient(azure_credential, subscription_id)

    # Fetch the VM details using the ARM ID
    vms = compute_client.virtual_machines.list(resource_group)
    vm_details = []
    for vm in vms:
        vm_details.append(get_vm_details(vm.id))
    return vm_details