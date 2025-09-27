import random 
import pandas as pd
import streamlit as st 
import nltk 
from nltk.tokenize import sent_tokenize, word_tokenize
from transformers import pipeline, T5Tokenizer
from sentence_transformers import SentenceTransformer, util

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")

try:
    nltk.data.find("taggers/averaged_perceptron_tagger")
except LookupError:
    nltk.download("averaged_perceptron_tagger")



@st.cache_data
def preprocess_text(text):
    #-------------NLTK--------------- 
    sent = sent_tokenize(text)
    all_words = []
    for s in sent:
        words = word_tokenize(s)
        for word in words:
            all_words.append(word)
    return sent,all_words

@st.cache_data
def generate_qa(text, sent, all_words, _generate, _qa):
    #-------------TRANSFORMERS--------------- 
    questions = []
    answers = []

    min_res_score = 0.7581
    for i, sen in enumerate(sent, start=1):
        result_q = _generate("generate question: " + sen)
        question_temp = result_q[0]['generated_text']
        question_temp = question_temp.replace("question:", "").strip()
        result_a = _qa(question=question_temp, context=text)
        if result_a['score'] >= min_res_score:
            questions.append(question_temp)
            answers.append(result_a['answer'])

    df = pd .DataFrame({"Question": questions,"Answer" : answers })

    return questions,answers,df

@st.cache_data
def generate_distractors(answers, all_words, df, _model ):
    #-------------SENTENCE-TRANSFORMERS--------------- 
    min_cos_score = 0.024
    max_cos_score = 0.975
    distractor_list = []
    for ans in answers:
        ans= ans.strip()
        ans_tag=nltk.pos_tag([ans])[0][1]
        ans_en = _model.encode(ans,convert_to_tensor=True)
        wrg_en = _model.encode(all_words,convert_to_tensor=True)

        cos_score = util.cos_sim(ans_en,wrg_en)
        similar = list(zip(all_words,cos_score[0]))
        similar_sort = sorted(similar,key=lambda x: -x[1])

        distractor = []
        set_distractor = set()
        for w,score in similar_sort:
            if w.lower() != ans.lower() and w.lower() not in set_distractor and nltk.pos_tag([w])[0][1]==ans_tag and min_cos_score<=score<=max_cos_score and w.lower() not in ans.lower():
               distractor.append(w)
               set_distractor.add(w.lower())
            if len(distractor) == 3:
                break
        distractor_list.append(distractor)

    option = []
    for i in range(len(answers)):
        option.append(random.sample([answers[i]] + distractor_list[i],k=4))
    df["Option"] = option

    return df,distractor_list

@st.cache_resource
def load_models():
    tokenizer = T5Tokenizer.from_pretrained(
        "mrm8488/t5-base-finetuned-question-generation-ap",
        legacy=False
    )

    model_01 = pipeline(
        "text2text-generation", 
        model="mrm8488/t5-base-finetuned-question-generation-ap",
        tokenizer=tokenizer,
        framework="pt")

    model_02 = pipeline(
        "question-answering",
        model="distilbert-base-cased-distilled-squad",
        tokenizer="distilbert-base-cased-distilled-squad",
        framework="pt")

    model_03 = SentenceTransformer('all-MiniLM-L6-v2')

    return model_01, model_02, model_03

def run_streamlit_ui():
    st.subheader("Here you go")
    
    # Initialize session state variables
    if "quiz_started" not in st.session_state:
        st.session_state.quiz_started = False
    if "q_idx" not in st.session_state:
        st.session_state.q_idx = 0
    if "score" not in st.session_state:
        st.session_state.score = 0
    if "answered" not in st.session_state:
        st.session_state.answered = False

    if st.session_state.quiz_started and st.session_state.q_idx < len(st.session_state.quiz_data):
        row = st.session_state.quiz_data.iloc[st.session_state.q_idx]

        with st.form(key="QUIZ"):
            st.markdown(f"**Question {st.session_state.q_idx + 1}**: {row['Question']}")
            user_ans = st.radio("Choose one", row["Option"], key=st.session_state.q_idx)
            submitted = st.form_submit_button("Submit")

        if submitted and not st.session_state.answered:
            if user_ans == row["Answer"]:
                st.write("Correct")
                st.session_state.score += 1
            else:
                st.write("Wrong answer")
                st.write("Correct answer: ", row["Answer"])
            st.session_state.answered = True

        if st.session_state.answered:
            if st.button("Next"):
                st.session_state.q_idx += 1
                st.session_state.answered = False
                st.rerun()

    elif st.session_state.q_idx >= len(st.session_state.quiz_data):
            st.write("**Quiz completed!**")
            st.write(f"Your score: {st.session_state.score} / {len(st.session_state.quiz_data)}")
            if st.button("Restart"):
                st.session_state.q_idx = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.session_state.quiz_started = False
                st.rerun()

def main():

    model_01, model_02, model_03 = load_models()

    if 'page' not in st.session_state:
        st.session_state.page= "input"
    
    st.title("AI QUIZ GENERATOR:")
    if st.session_state.page == "input":
        user_text = st.text_area("Paste the text here",height=300)

        if st.button("Generate Quiz"):
            if user_text:
                sent, all_words = preprocess_text(user_text)
                questions, answers, df = generate_qa(user_text,sent,all_words,model_01,model_02)
                new_df, distractor_list = generate_distractors(answers,all_words, df, model_03)
                st.session_state.quiz_data = new_df
                st.session_state.quiz_started = True
                st.session_state.page = "quiz"
                st.rerun()
            else:
                st.error("Please provide text")
                return

    if st.session_state.page == "quiz":  
        if 'quiz_data' in st.session_state:
            new_df= st.session_state.quiz_data
            run_streamlit_ui()
            if st.button("Back to Input"):
                st.session_state.quiz_started = False
                st.session_state.q_idx = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.session_state.page = "input"
                return

if __name__== "__main__":
    main()