import streamlit as st
from streamlit_chat import message
from utils import *
import os
from dotenv import load_dotenv
load_dotenv()
import openai

st.title("ASR Copilot")
st.subheader("AI Tutor:")
#col1, col2 = st.columns(2)

#with col1:
feature = st.selectbox(
    "Select a feature you want help with",
    ("","faq", "pricing")
)

st.session_state['current_feature'] = feature

if feature == "pricing":
    vm_arm_id_input = st.text_input("If you want to check the pricing for vm, provide the vm arm id.", key="vm_arm_id_input")
    rg_arm_id_input = st.text_input("If you want to check the pricing for multiple vms in a resource group, provide the resource group arm id.", key="rg_arm_id_input")
    if st.button("Get Pricing"):
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
        with st.spinner("Getting pricing for vms..."):
            vm_details = []
            if vm_arm_id_input:
                vm_details.append(get_vm_details(vm_arm_id_input))
            if rg_arm_id_input:
                vm_details.extend(get_vm_details_rg(rg_arm_id_input))
            st.session_state['vm_details'] = vm_details
    if 'vm_details' in st.session_state:
        st.write(st.session_state['vm_details'])
        if 'first_response' not in st.session_state:
            st.session_state['messages'] = get_initial_message()
            messages = st.session_state['messages']
            response = get_chatgpt_response(messages)
            st.session_state['first_response'] = response
            messages = update_chat(messages, "assistant", response)
        st.write(st.session_state['first_response'])
        
    # with col2:
    if 'vm_details' in st.session_state:
        if 'generated' not in st.session_state:
            st.session_state['generated'] = []
        if 'past' not in st.session_state:
            st.session_state['past'] = []

        query = st.text_input("Query: ", key="input")

        if query:
            with st.spinner("generating..."):
                messages = st.session_state['messages']
                messages = update_chat(messages, "user", query)
                response = get_chatgpt_response(messages)
                messages = update_chat(messages, "assistant", response)
                st.session_state.past.append(query)
                st.session_state.generated.append(response)
        
        if st.session_state['generated']:

            for i in range(len(st.session_state['generated'])-1, -1, -1):
                message(st.session_state["generated"][i], key=str(i))
                message(st.session_state['past'][i], is_user=True, key=str(i) + '_user')
                

            with st.expander("Show Messages"):
                st.write(messages)

if feature == "faq":
    if 'faq_init' not in st.session_state:
        with st.spinner("Generating indexes and setting the context..."):
            clear_cache()
            set_faq_context()
            st.session_state['faq_init'] = True
        
    query = st.text_input("Query: ", key="input")
    if query:
        with st.spinner("generating..."):
            answer = answerQuestion(query)
            if 'generated' not in st.session_state:
                st.session_state['generated'] = []
            if 'past' not in st.session_state:
                st.session_state['past'] = []
            st.session_state.past.append(query)
            st.session_state.generated.append(answer)
        
        if st.session_state['generated']:
            for i in range(len(st.session_state['generated'])-1, -1, -1):
                message(st.session_state["generated"][i], key=str(i))
                message(st.session_state['past'][i], is_user=True, key=str(i) + '_user')