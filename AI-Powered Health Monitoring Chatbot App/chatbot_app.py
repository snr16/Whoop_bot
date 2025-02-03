import anthropic
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import psycopg2
import streamlit as st
import time
from anthropic import APIError
import os
import tempfile
import textwrap
import traceback
import re
from streamlit_extras.stylable_container import stylable_container
import base64
import requests
import streamlit.components.v1 as components
import uuid

# Initialize the Claude client
client = anthropic.Anthropic(
    api_key="YOUR-API-KEY-GOES-HERE"
)

# Step 1: Generate SQL Query
@st.cache_data
def parse_intent(user_prompt):
    """Send user query to Claude using Messages API and get SQL query."""
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=1000,
        temperature=0,
        system="You are a SQL query builder for a PostgreSQL database. "
               "Respond only with a valid SQL query and nothing else including explanation. Do not give anything other than the code itself.",
        messages=[
        {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""
                            Write an SQL query for the following request:
                            The database contains the following tables: 
                            - users (user_id, first_name, last_name, email)
                            - sleep_data (user_id, total_sleep_time, rem_sleep_time, deep_sleep_time, efficiency, timestamp, nap, respiratory_rate)
                            - recovery_data (cycle_id, user_id, recovery_score, resting_heart_rate, hrv_rmssd_milli, created_at)
                            - cycle_data (cycle_id, user_id, strain, kilojoule, average_heart_rate, max_heart_rate, created_at)
                            - workout_data (workout_id, user_id, strain, kilojoule, distance_meter, created_at)
                            - body_measurements (user_id, height_meter, weight_kilogram, max_heart_rate)
                            The user_id is 21406427.
                            
                            Write an SQL query for: '{user_prompt}'.
                            """
                        }
                    ]
                }
            ]
        )
    return response.content[0].text

# Step 2: Execute SQL Query
@st.cache_data
def execute_postgresql_query(sql_query, db_config):
    """Execute SQL query on PostgreSQL database."""
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        return pd.DataFrame(results, columns=colnames)
    except Exception as e:
        return None

# Step 3: Generate Verbal Insight
@st.cache_data
def generate_insight(data):
    """Generate verbal insights based on the query results."""
    data_sample = data.to_string(index=False)
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=250,
        system="You are a data analysis assistant providing concise insights based on data.",
        messages=[
            {"role": "user", "content": f"Summarize the key insights from the following data:\n{data_sample}"}
        ]
    )
    return response.content[0].text

# Step 4: Generate Suggestions
def generate_suggestions(insight):
    """Generate actionable suggestions based on the insight."""
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=200,
        system="You are a health advisor providing suggestions based on insights.",
        messages=[
            {"role": "user", "content": f"Based on this insight: {insight}, what suggestions do you have for the user?"}
        ]
    )
    return response.content[0].text

# Step 5: Generate Visualization Code
def generate_visualization_code(prompt, data, retries=3):
    """Generate visualization code with retries."""
    data_sample = data.head(5).to_string(index=False)
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=500,
                system="You are a Python visualization assistant. Respond only with valid Python code for creating a visualization. "
                       "The data is already loaded into a Pandas DataFrame called 'data'. Do not add the text ``` or the word 'python' in the code output. Make sure the image size is 6 x 6 always.Ensure you save the plot as 'visualization_output.png'.",
                messages=[
                    {"role": "user", "content": f"Create a visualization for the following data:\n{data_sample}\n\n{prompt}"}
                ]
            )
            return response.content[0].text
        except APIError as e:
            if attempt < retries - 1:
                time.sleep(2)  # Wait and retry
                print(f"Retry {attempt + 1} after error: {e}")
            else:
                st.error("There was an issue generating the visualization after multiple attempts. Please try again later.")
                print(f"Final Error: {e}")
                return None


# Visualization Execution Function
def execute_visualization_and_save(code, data, output_file="visualization.png"):
    """
    Execute the visualization code after modifying plt.savefig to use a persistent file path.
    """
    try:
        # Persistent file path
        output_dir = os.path.join(os.getcwd(), "visualizations")
        os.makedirs(output_dir, exist_ok=True)  # Ensure the directory exists
        persistent_file_path = os.path.normpath(os.path.join(output_dir, output_file))

        
        # Preprocess DataFrame: Convert datetime strings to numerical timestamps
        for col in data.columns:
            if pd.api.types.is_object_dtype(data[col]) or pd.api.types.is_datetime64_any_dtype(data[col]):
                try:
                    # Convert to datetime and then to Unix timestamp
                    data[col] = pd.to_datetime(data[col], errors="coerce").astype(int) / 10**9
                except Exception as e:
                    print(f"Error converting column {col}: {e}")

        # Clean up the generated code
        code = re.sub(r"plt\.show\(\)", "", code)  # Remove plt.show()

        # Replace plt.savefig path dynamically (fix unmatched parenthesis issue)
        if "plt.savefig" in code:
            escaped_path = persistent_file_path.replace("\\", "\\\\")  # Escape backslashes
            code = re.sub(
                r"plt\.savefig\(['\"].*?['\"]\)",  # Match plt.savefig('path/to/file.png')
                f"plt.savefig(r'{escaped_path}')",  # Replace with safe escaped path
                code
            )
        else:
            # Append plt.savefig if it doesn't exist
            save_code = textwrap.dedent(f"""
            plt.savefig(r'{persistent_file_path}', bbox_inches='tight')
            plt.close()
            """).strip()
            code = f"{code}\n{save_code}"

        # Debug: Print the final code for confirmation
        print("Generated Visualization Code:\n", code)

        # Execute the modified code safely
        compiled_code = compile(code, "<string>", "exec")
        local_vars = {"data": data, "pd": pd, "sns": sns, "plt": plt}
        exec(compiled_code, {}, local_vars)

        # Verify if the file was created
        if os.path.exists(persistent_file_path):
            print("File successfully created:", persistent_file_path)
            return True, persistent_file_path
        else:
            return False, "Visualization file was not created."

    except Exception as e:
        # Return error traceback for easier debugging
        error_message = traceback.format_exc()
        print("Error Traceback:\n", error_message)
        return False, error_message

    
# Step 6: Generate Diet Suggestions
def generate_diet_suggestions(insight, data_sample):
    """Generate diet suggestions based on the data insights."""
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=300,
        system="You are a health advisor specializing in nutrition. Provide diet suggestions tailored to user data insights.",
        messages=[
            {"role": "user", "content": f"Based on the following health data: {data_sample}, "
                                        f"and this insight: '{insight}', provide personalized diet suggestions."}
        ]
    )
    return response.content[0].text
    


# Helper function to create a stylable button container

def create_stylable_button(style_name, label, key):
    styles = {
        "green": """
            button {
                background-color: #00FF00;
                color: black;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover {
                background-color: #00CC00;
            }
        """,
        "red": """
            button {
                background-color: #FF0000;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover {
                background-color: #CC0000;
            }
        """,
        "blue": """
            button {
                background-color: #1E90FF;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover {
                background-color: #1C86EE;
            }
        """,
        "dark-green": """
            button {
                background-color: #32CD32;
                color: white;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 16px;
                cursor: pointer;
            }
            button:hover {
                background-color: #2E8B57;
            }
        """
    }

    # Dynamically load the required style
    css_style = styles.get(style_name, "")

    with stylable_container(style_name, css_styles=css_style):
        return st.button(label, key=key)


db_config = {
    "database": "health_monitor_whoop",
    "user": "USERNAME",
    "password": "PASSWORD",
    "host": "PUBLIC-IP-OF-THE-DB",
    "port": "5432"
}


# Streamlit Chatbot Interface
def main():
    try:
        # Load background image and chatbot image as base64
        background_image_path = "D:/GenAI_Project/background.jpg"
        chatbot_image_path = "D:/GenAI_Project/bot.png"

        base64_background_image = get_image_base64(background_image_path)
        base64_chatbot_image = get_image_base64(chatbot_image_path)

        # General page styling for other elements (not the chatbot)
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: 
                    linear-gradient(rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.3)), 
                    url("data:image/png;base64,{base64_background_image}");
                background-size: cover;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}

            /* Style buttons and expanders */
            button, .stButton > button {{
                color: white !important;
                background: linear-gradient(135deg, #6DD5ED, #2193B0);
                border-radius: 8px;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.3);
                transition: all 0.3s ease;
            }}

            button:hover {{
                background: linear-gradient(135deg, #57C6E1, #1E86A5);
                transform: scale(1.05);
            }}

            /* Style for st.expander */
            .stExpander {{
                background: linear-gradient(to bottom, #2C3E50, #4A5568);
                color: #F0F8FF;
                border-radius: 10px !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Custom HTML for the chatbot image
        chatbot_html = f"""
        <style>
        .chatbot-image {{
            width: auto;
            max-width: 100%;
            height: auto;
            transition: transform 0.3s ease-out;
        }}
        .chatbot-image:hover {{
            transform: scale(1.3);
        }}
        </style>
        <img src="data:image/png;base64,{base64_chatbot_image}" class="chatbot-image" />
        """

        # Layout
        _, col1, col2, _ = st.columns([0.01, 0.28, 0.75, 0.01])

        with col1:
            st.components.v1.html(chatbot_html, height=400)

        with col2:
            st.title("AI-Powered WHOOP Health Monitoring Chatbot")
            st.write("Ask about your health data insights, visualizations, or suggestions.")

            # Initialize session state
            if "conversations" not in st.session_state:
                st.session_state.conversations = []

            if "current_convo" not in st.session_state:
                st.session_state.current_convo = {
                    "user_input": None,
                    "user_input_processed":False,
                    "insight": None,
                    "data": None,
                    "selected_action": None,
                    "viz_displayed": None,
                    "viz_code": None,
                }

            # Display previous conversations
            if st.session_state.conversations:
                st.write("### Previous Conversations")
                for i, convo in enumerate(st.session_state.conversations):
                    with st.expander(f"Conversation {i+1}"):
                        display_conversation(convo)

            # Main logic
            initialize_and_run()

    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")
        print(e)



def get_image_base64(image_path):
    """Read an image file and convert it to a base64 string."""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def display_conversation(convo):
    """Display a past conversation stored in the session state."""

    # Apply Custom CSS
    st.markdown(
        """
        <style>
        /* Style for user input */
        .user-message {
            background-color: #D9EFFF; /* Light blue background */
            color: #0B3D91; /* Dark blue text */
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
            font-family: Arial, sans-serif;
        }

        /* Style for assistant insights */
        .assistant-insight {
            background-color: #E6F4EA; /* Light green background */
            color: #1E5631; /* Dark green text */
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
            font-family: Arial, sans-serif;
        }

        /* Style for suggestions */
        .suggestions-box {
            background-color: #FFF8E1; /* Light yellow background */
            color: #8B8000; /* Darker yellow text */
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
            font-family: Arial, sans-serif;
        }

        /* Style for diet suggestions */
        .diet-suggestions-box {
            background-color: #FADBD8; /* Light red background */
            color: #8B8000; /* Darker yellow text */
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 8px;
            box-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
            font-family: Arial, sans-serif;
        }


        /* Style for images */
        .styled-image img {
            border-radius: 10px;
            box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
            margin-top: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Display User Input
    if convo["user_input"]:
        st.markdown(f'<div class="user-message"><strong>You:</strong> {convo["user_input"]}</div>', unsafe_allow_html=True)

    # Display Insights
    if convo["insight"]:
        st.markdown(f'<div class="assistant-insight"><strong>Insight:</strong> {convo["insight"]}</div>', unsafe_allow_html=True)

    # Display Suggestions
    if "suggestions" in convo and convo["suggestions"]:
        st.markdown(f'<div class="suggestions-box"><strong>Suggestions:</strong> {convo["suggestions"]}</div>', unsafe_allow_html=True)

    # Display Diet Suggestions
    if "diet_suggestions" in convo and convo["diet_suggestions"]:
        st.markdown(f'<div class="diet-suggestions-box"><strong>Diet Suggestions:</strong> {convo["diet_suggestions"]}</div>', unsafe_allow_html=True)

    # Display Visualization Images
    if "viz_code" in convo and "viz_image" in convo and convo["viz_image"]:
        st.markdown('<div class="styled-image">', unsafe_allow_html=True)
        st.image(convo["viz_image"], caption="Generated Visualization")
        st.markdown('</div>', unsafe_allow_html=True)



def reset_session_state():
    """Reset current conversation state."""
    st.session_state.current_convo = {
        "user_input": None,
        "user_input_processed":False,
        "insight": None,
        "data": None,
        "selected_action": None,
        "viz_displayed": None,
        "viz_code": None,
        "viz_image":None
    }
    st.rerun()


def initialize_and_run():
    """Initialize and manage user input, insights, and UI actions."""

    # Ensure 'current_convo' and flags are initialized properly
    if "current_convo" not in st.session_state:
        st.session_state.current_convo = {
            "user_input": None,
            "data": None,
            "insight": None,
            "user_input_processed": False,
            "selected_action": None
        }

    # Input key for dynamic text input
    input_key = f"user_input_{len(st.session_state.conversations)}"

    # User Input for Query
    user_input = st.text_input("You:", key=input_key)

    if user_input and not st.session_state.current_convo["user_input_processed"]:
        try:
            st.session_state.current_convo["user_input"] = user_input
            st.write("Fetching data, please wait...")

            # Step 1: Generate SQL query
            sql_query = parse_intent(user_input)
            st.session_state.current_convo["data"] = execute_postgresql_query(sql_query, db_config)

            print("\nGenerated SQL Query:", sql_query)
            print("\nFetched Data:", st.session_state.current_convo["data"])

            # Step 2: Generate Insight
            if st.session_state.current_convo["data"] is not None and not st.session_state.current_convo["data"].empty:
                st.session_state.current_convo["insight"] = generate_insight(st.session_state.current_convo["data"])
                st.session_state.current_convo["user_input_processed"] = True
                st.rerun()

        except Exception as e:
            st.error(f"An error occurred: {e}")

    # Show insights and buttons only after input is processed
    if st.session_state.current_convo["user_input_processed"]:
        st.success(f"**Insight:** {st.session_state.current_convo['insight']}")

        # Render buttons only if action is not already selected
        _, col1, col2, col3, _ = st.columns([0.05, 0.3, 0.3, 0.3, 0.05])

        with col1:
            if st.button("Generate Suggestions", key="suggestions_btn"):
                st.session_state.current_convo["selected_action"] = "Generate Suggestions"
                st.rerun()
        with col2:
            if st.button("Generate Diet Suggestions", key="diet_btn"):
                st.session_state.current_convo["selected_action"] = "Generate Diet Suggestions"
                st.rerun()
        with col3:
            if st.button("Generate Visualization", key="visualization_btn"):
                st.session_state.current_convo["selected_action"] = "Generate Visualization"
                st.rerun()

    # Handle selected actions
    if st.session_state.current_convo["selected_action"] == "Generate Suggestions":
        handle_suggestions()
    elif st.session_state.current_convo["selected_action"] == "Generate Diet Suggestions":
        handle_diet_suggestions()
    elif st.session_state.current_convo["selected_action"] == "Generate Visualization":
        handle_visualizations()



def handle_suggestions():
    # if st.session_state.current_convo["insight"]:
        # Ensure suggestions_iteration exists in the current conversation state
        if "suggestions_iteration" not in st.session_state.current_convo:
            st.session_state.current_convo["suggestions_iteration"] = 0

        # Generate and display suggestions
        suggestions = generate_suggestions(st.session_state.current_convo['insight'])
        st.info(f"**Suggestions:** {suggestions}")

        # Save the suggestions in the current conversation
        st.session_state.current_convo["suggestions"] = suggestions

        # Feedback section
        col1, col2,_ = st.columns([0.3,0.15,0.55], vertical_alignment='center')
        with col1:
            st.write("Are you satisfied with the suggestions?")
        with col2:
            thumbs_down = st.button("No", key=f"thumbs_down_{st.session_state.current_convo['suggestions_iteration']}")

        # Logic for "No" - Generate more suggestions
        if thumbs_down:
            st.session_state.current_convo["suggestions_iteration"] += 1


        # Divider and End Suggestions Button
        _,center_col,_ = st.columns([0.3,0.4,0.3])
        with center_col:
            st.divider()
            if st.button("End Suggestions and Start New Conversation", key="end_suggestions_button"):
                # Save current conversation to the conversations list
                if "conversations" not in st.session_state:
                    st.session_state.conversations = []
                st.session_state.conversations.append(st.session_state.current_convo)

                # Reset the current conversation state
                st.session_state.current_convo = {
                    "user_input": None,
                    "insight": None,
                    "data": None,
                    "user_input_processed":False,
                    "selected_action": None,
                    "suggestions": None,
                    "suggestions_iteration": 0,
                    "viz_code": None,
                    "viz_prompt": None,
                    "viz_displayed": None,
                    "viz_image": None,
                }
                st.rerun()

def handle_diet_suggestions():
    # if st.session_state.current_convo["insight"]:
        # Ensure diet_suggestions_iteration exists in the current conversation state
        if "diet_suggestions_iteration" not in st.session_state.current_convo:
            st.session_state.current_convo["diet_suggestions_iteration"] = 0

        # Generate and display diet suggestions
        data_sample = st.session_state.current_convo["data"].head(5).to_string(index=False)
        diet_suggestions = generate_diet_suggestions(
            st.session_state.current_convo["insight"], data_sample
        )
        st.info(f"**Diet Suggestions:**\n{diet_suggestions}")

        # Save the diet suggestions in the current conversation
        st.session_state.current_convo["diet_suggestions"] = diet_suggestions

        # Feedback section
        col1, col2, _ = st.columns([0.3, 0.15, 0.55], vertical_alignment='center')
        with col1:
            st.write("Are you satisfied with the diet suggestions?")
        with col2:
            thumbs_down = st.button(
                "No", key=f"diet_thumbs_down_{st.session_state.current_convo['diet_suggestions_iteration']}"
            )

        # Logic for "No" - Generate more diet suggestions
        if thumbs_down:
            st.session_state.current_convo["diet_suggestions_iteration"] += 1


        # Divider and End Diet Suggestions Button
        _, center_col, _ = st.columns([0.3, 0.4, 0.3])
        with center_col:
            st.divider()
            if st.button("End Diet Suggestions and Start New Conversation", key="end_diet_suggestions_button"):
                # Save current conversation to the conversations list
                if "conversations" not in st.session_state:
                    st.session_state.conversations = []
                st.session_state.conversations.append(st.session_state.current_convo)

                # Reset the current conversation state
                st.session_state.current_convo = {
                    "user_input": None,
                    "insight": None,
                    "data": None,
                    "selected_action": None,
                    "user_input_processed":False,
                    "diet_suggestions": None,
                    "diet_suggestions_iteration": 0,
                    "viz_code": None,
                    "viz_prompt": None,
                    "viz_displayed": None,
                    "viz_image": None,
                }
                st.rerun()



def handle_visualizations():
    if st.session_state.current_convo["data"] is not None:
        # Input chart type for visualization
        viz_prompt = st.text_input("Enter the type of visualization (e.g., bar chart, line chart):", 
                                   key=f"viz_type_{st.session_state.current_convo.get('suggestions_iteration', 0)}")

        if viz_prompt:
            # Generate Visualization Code
            if "viz_code" not in st.session_state.current_convo or st.session_state.current_convo.get("viz_prompt") != viz_prompt:
                st.session_state.current_convo["viz_prompt"] = viz_prompt
                st.session_state.current_convo["viz_code"] = generate_visualization_code(
                    viz_prompt, st.session_state.current_convo["data"]
                )

            if st.session_state.current_convo["viz_code"]:

                unique_filename = f"viz_{uuid.uuid4().hex}.png"

                # Execute and Display Visualization
                success, result = execute_visualization_and_save(
                    st.session_state.current_convo["viz_code"], 
                    st.session_state.current_convo["data"],
                    unique_filename
                )

                if success:
                    st.image(result, caption="Generated Visualization")
                    st.session_state.current_convo["viz_displayed"] = True
                    st.session_state.current_convo["viz_image"] = result
                else:
                    st.error("Failed to generate visualization.")

                # Buttons to Show Code or Skip
                _,col1,col2,_ = st.columns([1,1,1,1])
                with col1:
                    show_code = create_stylable_button("green", "Show Code", key=f"show_code_{st.session_state.current_convo.get('suggestions_iteration', 0)}")
                with col2:
                    skip_code = create_stylable_button("red", "Skip Code", key=f"skip_code_{st.session_state.current_convo.get('suggestions_iteration', 0)}")

                # Handle Button Actions
                if show_code:
                    st.text_area("Generated Visualization Code:", 
                                 value=st.session_state.current_convo["viz_code"], 
                                 height=300)
                if skip_code:
                    st.write("Okay! Let us know if you need further assistance.")

                # Save the conversation and start a new one
                _,center_col,_ = st.columns([1,3,1])
                with center_col:
                    st.divider()
                    if st.button("End Visualization and Start New Conversation", key="end_visualizations_button"):
                        # Save the current conversation
                        if "conversations" not in st.session_state:
                            st.session_state.conversations = []
                        st.session_state.conversations.append(st.session_state.current_convo)

                        # Reset the current conversation state
                        st.session_state.current_convo = {
                            "user_input": None,
                            "user_input_processed":False,
                            "insight": None,
                            "data": None,
                            "selected_action": None,
                            "suggestions": None,
                            "suggestions_iteration": 0,
                            "viz_code": None,
                            "viz_prompt": None,
                            "viz_displayed": None,
                            "viz_image": None,
                        }
                        st.rerun()

            else:
                st.write("Failed to get Visualization code.")


# Run the Streamlit app
if __name__ == "__main__":
    main()
