from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import os
from flask import Flask, jsonify, request
import threading
import json
from datetime import datetime
from pathlib import Path
import pandas as pd
import sys



# Lock file check
def is_already_running():
    lockfile = Path("/tmp/telegram_bot.lock")
    
    if lockfile.exists():
        try:
            with open(lockfile) as f:
                pid = int(f.read())
            os.kill(pid, 0)  # Check if process is running
            return True
        except (OSError, ValueError):
            lockfile.unlink(missing_ok=True)
    
    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))
    return False



# Create Flask app
app = Flask(__name__)



# Create directories for storage
DATA_DIR = Path("bot_data")
DATA_DIR.mkdir(exist_ok=True)

JOURNALS_DIR = DATA_DIR / "learning_journals"
JOURNALS_DIR.mkdir(exist_ok=True)

USERS_DIR = DATA_DIR / "users"
USERS_DIR.mkdir(exist_ok=True)

FEEDBACK_DIR = DATA_DIR / "feedback"
FEEDBACK_DIR.mkdir(exist_ok=True)

# Configure admin users
ADMIN_IDS = [
    471827125,  # add other admin Telegram user ID
]

class UserManager:
    @staticmethod
    def save_user_info(user):
        """Save user information when they start using the bot"""
        user_file = USERS_DIR / f"user_{user.id}.json"
        user_data = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "joined_date": datetime.now().isoformat(),
            "current_lesson": "lesson_1",
            "completed_lessons": []
        }
        
        with open(user_file, 'w') as f:
            json.dump(user_data, f, indent=2)
        return user_data

    @staticmethod
    def get_user_info(user_id):
        """Get user information"""
        user_file = USERS_DIR / f"user_{user_id}.json"
        if user_file.exists():
            with open(user_file) as f:
                return json.load(f)
        return None

    @staticmethod
    def update_user_progress(user_id, lesson_key):
        """Update user's progress"""
        user_file = USERS_DIR / f"user_{user_id}.json"
        if user_file.exists():
            with open(user_file) as f:
                user_data = json.load(f)
            
            user_data["current_lesson"] = lesson_key
            if lesson_key not in user_data["completed_lessons"]:
                user_data["completed_lessons"].append(lesson_key)
            
            with open(user_file, 'w') as f:
                json.dump(user_data, f, indent=2)

class FeedbackManager:
    @staticmethod
    def save_feedback(user_id, feedback_text):
        """Save user feedback"""
        feedback_file = FEEDBACK_DIR / f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id}.json"
        feedback_data = {
            "user_id": user_id,
            "feedback": feedback_text,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(feedback_file, 'w') as f:
            json.dump(feedback_data, f, indent=2)

    @staticmethod
    def get_all_feedback():
        """Get all feedback"""
        feedback_list = []
        for feedback_file in FEEDBACK_DIR.glob("feedback_*.json"):
            with open(feedback_file) as f:
                feedback_list.append(json.load(f))
        return feedback_list

# Task Manager using local JSON storage (could be replaced with Google Sheets integration)
class TaskManager:
    TASKS_FILE = DATA_DIR / "tasks.json"
    
    @staticmethod
    def load_tasks():
        """Load tasks from storage"""
        if TaskManager.TASKS_FILE.exists():
            with open(TaskManager.TASKS_FILE) as f:
                return json.load(f)
        return {"tasks": []}

    @staticmethod
    def get_tasks_for_lesson(lesson_key):
        """Get relevant tasks for a lesson"""
        tasks = TaskManager.load_tasks()
        return [task for task in tasks["tasks"] 
                if task["lesson"] == lesson_key and task["is_active"]]



# Simple file-based storage for learning journals
JOURNALS_DIR = Path("learning_journals")
JOURNALS_DIR.mkdir(exist_ok=True)

def save_journal_entry(user_id, lesson_key, response):
    """Save a user's response to their journal file"""
    journal_file = JOURNALS_DIR / f"journal_{user_id}.json"
    
    # Load existing journal or create new one
    if journal_file.exists():
        with open(journal_file) as f:
            journal = json.load(f)
    else:
        journal = {
            "user_id": user_id,
            "entries": []
        }
    
    # Add new entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "lesson": lesson_key,
        "response": response
    }
    journal["entries"].append(entry)
    
    # Save updated journal
    with open(journal_file, 'w') as f:
        json.dump(journal, f, indent=2)



@app.route('/')
def home():
    return "Bot is running!"



# Add routes to view journals
@app.route('/journals/<user_id>')
def view_journal(user_id):
    journal_file = JOURNALS_DIR / f"journal_{user_id}.json"
    if journal_file.exists():
        with open(journal_file) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "Journal not found"}), 404



@app.route('/journals')
def list_journals():
    journals = []
    for journal_file in JOURNALS_DIR.glob("journal_*.json"):
        with open(journal_file) as f:
            journals.append(json.load(f))
    return jsonify(journals)



# Define the lessons and steps
lessons = {
    "lesson_1": {
        "text": """👋 Hello and welcome!

We're excited to help you learn how to build and grow products by leveraging communities. Here's how this will work:

✨ You'll complete a series of tasks designed to teach mental models for building your own processes. These mental models include:

- 🧠 Design Thinking
- 📊 Business Model Thinking
- 🌍 Market Thinking
- 👤 User Thinking
- 🏗️ Agile Project Thinking

Let's start with Design Thinking! Ready? Reply ✅ to continue.""",
        "next": "lesson_2"
    },
    "lesson_2": {
        "text": """🧠 Lesson 2: Design Thinking

👋 Welcome to Design Thinking! This lesson helps you learn and apply the 5-step process for understanding and solving user problems. Here's the breakdown:

1️⃣ Empathise: Understand your user's perspective and feelings
2️⃣ Define: Identify the core problem or challenge
3️⃣ Ideate: Brainstorm creative solutions
4️⃣ Prototype: Develop an initial version of your solution
5️⃣ Test: Get user feedback and refine your ideas

🌟 Exercise Focus: Redesign the experience of gift-giving for someone close to you (not the gift itself). Ready? Reply ✅ to begin.""",
        "next": "lesson_2_step_1"
    },
    "lesson_2_step_1": {
        "text": """🔍 Understanding your user is key! To start, find someone you can interview. This could be a friend, sibling, or colleague. They will be your "user" throughout this exercise.

✅ Prep Task:
1. Get a notebook or voice recorder to capture their responses.
2. Ask about their last gift-giving experience:
   - "What happened?"
   - "How did you choose the gift?"
   - "What was hard or easy about the process?"

📝 Note interesting points. Share one insight you found surprising!""",
        "next": "lesson_2_step_2"
    },
    "lesson_2_step_2": {
        "text": """💬 Follow up and dig deeper! Ask more questions about responses you found interesting. Use open-ended questions like "Why was that challenging?" or "How did that make you feel?"

🔥 Tip: Ask "Why?" multiple times until you uncover deeper feelings or emotions.

📚 Resource: Read this article on the 5 Whys (https://en.wikipedia.org/wiki/5_Whys) to understand why asking "Why" is so powerful in design.

Reply 📝 with one new insight you gained during this follow-up.""",
        "next": "lesson_2_step_3"
    },
    "lesson_2_step_3": {
        "text": """📌 Let's clarify the problem. Using your notes, create a concise problem statement. Here's how:

✅ Tasks:
1. Write a Needs List: What was your user trying to accomplish?
   - What were they trying to do by going through that experience. What does gift giving do for them. Needs should be verbs.
2. Write an Insights List: What stood out to you during the interview?
   - These are the things you noticed would be helpful in improving that experience for your user.
3. Combine items in both the Needs List and the Insights List to craft a Problem Statement:
   - Example: "Ali needs a way to make the most of his time (Need), but he struggles with managing it effectively (Insight)."

Here's a template you can use by filling in the blanks/[ text ]:
- [UserName] needs/wants a way to [user need], surprisingly // because // but [insight].

Reply ✏️ with your problem statement for feedback!""",
        "next": "lesson_2_step_4"
    },
    "lesson_2_step_4": {
        "text": """💡 Time to get creative! Brainstorm possible solutions to the problem you defined.

✅ Tasks:
1. Write down at least 3 possible solutions (apps, services, or creative approaches).
2. Need inspiration? Check out these resources:
   - How to Build Creative Confidence: https://youtu.be/16p9YRF0l-g
   - How to Generate Ideas: https://youtu.be/L1kbrlZRDvU
   - Develop an Eye for Design: https://medium.com/@kathleen_warner/how-to-develop-an-eye-for-design-c5a4c64bb26c
   - Stealing Your Way to Original Designs: https://danmall.com/posts/stealing-your-way-to-original-designs/

Reply 💡 with your list of ideas.""",
        "next": "lesson_2_step_5"
    },
    "lesson_2_step_5": {
        "text": """🛠️ Bring your idea to life! Use your top solution to create a simple prototype. Sketch it out on paper or use a free tool like MarvelApp (https://marvelapp.com/) to create an interactive wireframe.

✅ Tasks:
- Share a brief description or photo of your prototype.
- Need help? Check out this guide on UX Sketching: https://www.toptal.com/designers/ux/guide-to-ux-sketching

Reply 📷 with your prototype or its description.""",
        "next": "lesson_2_step_6"
    },
    "lesson_2_step_6": {
        "text": """🔄 Refine your idea with feedback! This is an ongoing process.

1. Show your prototype to your user.
2. Ask:
   - "What works well for you?"
   - "What doesn't work or feels unclear?"

✅ Task: Use their feedback to refine your prototype.

Repeat this process as needed, but don't aim for perfection---focus on real-world feedback! You are not looking to validate your solution, you just want feedback.

Reply 📝 with one key improvement you made based on testing.

🌟 Congratulations! You've completed the Design Thinking process! Remember, it's a cycle: Empathise, Define, Ideate, Prototype, and Test repeatedly to create great solutions.

Are you ready to move to Lesson 3 on Business Modelling? Reply ✅ to proceed!""",
        "next": "lesson_3"
    },
    "lesson_3": {
        "text": """📊 Lesson 3: Business Modelling

👋 Welcome to Business Modelling! This lesson introduces the Business Model Canvas, a strategic tool for creating and documenting business models. You'll apply this to the idea you worked on in the Design Thinking lesson.

🎥 Videos to Watch:
1. Quick Overview of the Business Model Canvas: https://www.youtube.com/watch?v=QoAOzMTLP5s
2. Getting From Business Idea to Business Model: https://www.youtube.com/watch?v=wwShFsSFb-Y
3. Visualising Your Business Model: https://www.youtube.com/watch?v=wlKP-BaC0jA
4. Prototyping Business Models: https://www.youtube.com/watch?v=iA5MVUNkSkM
5. Navigating Your Environment: https://www.youtube.com/watch?v=7O36YBn9x_4
6. Proving It: Testing Business Models: https://www.youtube.com/watch?v=-2gd_vhNYT4
7. Telling Your Story: https://www.youtube.com/watch?v=SshglHDKQCc

✅ Task: Watch the videos in order. Reply ✅ once done.""",
        "next": "lesson_3_step_2"
    },
    "lesson_3_step_2": {
        "text": """📖 The Business Model Canvas includes 9 key components:

- Value Proposition
- Customer Segments
- Revenue Streams
- Channels
- Cost Structure
- Key Activities
- Key Resources
- Key Partnerships
- Customer Relationships

✍️ Task: Take the idea you worked on during the Design Thinking lesson and begin filling in the Business Model Canvas. Focus on:
1️⃣ Value Proposition: What problem does your product solve?
2️⃣ Customer Segments: Who are you solving this problem for?

Reply 📝 with your notes for these two components.""",
        "next": "lesson_3_step_3"
    },
    "lesson_3_step_3": {
        "text": """🔄 A business model should evolve based on feedback and testing.

✅ Tasks:
1. Map your business's environment: Consider competitors, trends, and external factors that affect your model.
2. Test assumptions for each component of the Canvas. For example:
   - Are your target customers willing to pay for this solution?
   - Are the chosen channels effective for reaching them?

Reply 📝 with one insight or change you made based on your tests.""",
        "next": "lesson_3_step_4"
    },
    "lesson_3_step_4": {
        "text": """📜 The final step is crafting a compelling narrative. Your story should explain:
- What your product does.
- Why it's needed.
- How it creates value.

✅ Task: Use your notes from the Canvas to write a 3-sentence pitch for your product.

Reply 📜 with your pitch.

🌟 Congratulations! You've completed Lesson 3: Business Modelling. You now know how to create, refine, and present a business model.

🚀 Next Step: Lesson 4 - Market Thinking. Ready? Reply ✅ to continue!""",
        "next": "lesson_4"
    },
    "lesson_4": {
        "text": """🌍 Lesson 4: Market Thinking

👋 Welcome to Market Thinking! Understanding your market is critical for aligning your product with user needs and growth channels. This lesson will guide you through Brian Balfour's Four Fit Framework, a powerful approach to structuring your business for sustainable growth.

💡 Explore the Four Fit Framework:
1️⃣ Product-Market Fit: Does your product solve a key problem for your target users?
2️⃣ Market-Channel Fit: Are your chosen channels effective for reaching your market?
3️⃣ Channel-Model Fit: Do your channels align with your revenue model?
4️⃣ Model-Market Fit: Does your revenue model work well within your target market?

📚 Start with these essays:
- Why Product-Market Fit Isn't Enough: https://brianbalfour.com/essays/product-market-fit-isnt-enough
- Market-Product Fit: The Road to a $100M Company Doesn't Start with Product: https://brianbalfour.com/essays/market-product-fit
- Product-Channel Fit Will Make or Break Your Growth Strategy: https://brianbalfour.com/essays/product-channel-fit-for-growth
- Channel-Model Fit: Get Out of the ARPU-CAC Danger Zone: https://brianbalfour.com/essays/channel-model-fit-for-user-acquisition
- Model-Market Fit Threshold for Growth: https://brianbalfour.com/essays/model-market-fit-threshold-for-growth
- How The Four Fits Work Together: https://brianbalfour.com/essays/key-lessons-for-100m-growth
- HubSpot Growth Framework Case Study: https://brianbalfour.com/essays/hubspot-growth-framework-100m

🎥 Prefer videos? Watch summaries embedded in the essays for a quick overview. Reply ✅ when you've completed the first essay.""",
        "next": "lesson_4_step_2"
    },
    "lesson_4_step_2": {
        "text": """🔄 Task: Using the product idea from your Design Thinking lesson, answer these:

1️⃣ Who are your target users? Define their demographics, behaviour, and pain points.
2️⃣ What channels will you use to reach them? Consider online, offline, and hybrid channels.

📝 Reply with your answers for feedback.""",
        "next": "lesson_4_step_3"
    },
    "lesson_4_step_3": {
        "text": """📌 Task: Reflect on your answers and evaluate:

- Does your product align well with your market's needs?
- Are the chosen channels scalable and effective?
- Does your revenue model work seamlessly within this framework?

Reply 📝 with one insight or adjustment you've made to improve your fit.

🌟 Congratulations! You've completed Lesson 4: Market Thinking. You now have the tools to align your product with its market, channels, and revenue model for maximum growth.

🚀 Next Step: Lesson 5 - User Thinking. Ready? Reply ✅ to continue!""",
        "next": "lesson_5"
    },
    "lesson_5": {
        "text": """👤 Lesson 5: User Thinking

👋 Welcome to User Thinking! Understanding why people do what they do and how they think is essential to building products they love. This lesson introduces user psychology and behaviour, equipping you with tools to create innovative, user-centred solutions.

🔍 What You’ll Learn:
1️⃣ How emotions influence actions and decisions.
2️⃣ How to use the Hooked Model to design habit-forming products.

🌟 Ready to dive in? Reply ✅ to start!""",
        "next": "lesson_5_step_1"
    },
    "lesson_5_step_1": {
        "text": """💡 Emotions drive decisions. Learning how emotions influence behaviour is key to designing better experiences.

✅ Tasks:
1. Watch these videos:
   - How emotions are an integral part of thinking and decision making: https://youtu.be/weuLejJdUu0
   - How emotions define people’s decisions: https://youtu.be/1wup_K2WN0I
   - Why good design makes us happy: https://www.youtube.com/watch?v=RlQEoJaLQRA

Write down one insight from each video.

📝 Reply with your three insights to proceed.""",
        "next": "lesson_5_step_2"
    },
    "lesson_5_step_2": {
        "text": """🧠 Create habit-forming products. The Hooked Model combines triggers, actions, rewards, and investment to build user engagement.

✅ Tasks:
1. Watch this 30-minute summary: How to Build Habit-Forming Products Using The Hook Model and BJ Fogg’s Behaviour Model: https://www.youtube.com/watch?v=RR9PnPr529k
2. Download and complete exercises in this workbook: https://drive.google.com/file/d/0B27e0z0T2hi2NmI5S0tqdWIwWHk2RlNNTWFMUVBxWEdsN1VF/view?usp=sharing

📝 Reply with one key takeaway from the video and workbook.""",
        "next": "lesson_5_step_3"
    },
    "lesson_5_step_3": {
        "text": """📖 Learn from Alexa’s success. Behaviour design can influence user habits significantly.

✅ Tasks:
1. Read this case study: How Amazon’s Alexa design changes our behaviour: https://medium.com/behavior-design/the-secret-behind-alexas-success-3188d473199c
2. Identify one tactic Alexa uses that you could apply to your own product.

📝 Reply with your observation.""",
        "next": "lesson_5_step_4"
    },
    "lesson_5_step_4": {
        "text": """📚 Master persuasive design. Use behaviour models to influence how users interact with your product.

✅ Tasks:
1. Read this paper: A Behaviour Model for Persuasive Design: https://drive.google.com/file/d/1jHrV9Ur8YrG-i3VDA8_rw6NCMtCB97LO/view?usp=sharing
2. Reflect on how you can apply these principles to your product.

📝 Reply with one application idea for your product.

🌟 Congratulations! You've completed Lesson 5: User Thinking. You now understand user psychology and behaviour, giving you tools to create solutions that resonate deeply with your audience.

🚀 Next Step: Lesson 6 - Agile Project Thinking. Ready? Reply ✅ to continue!""",
        "next": "lesson_6"
    },
    "lesson_6": {
        "text": """🏗️ Lesson 6: Project Thinking

👋 Welcome to Project Thinking! This lesson combines principles from Agile and traditional project management to help you execute your business ideas efficiently and effectively.

🔍 What You’ll Learn:
1️⃣ How to scope and plan your work.
2️⃣ How to use milestones and tasks to track progress.
3️⃣ How to prioritise, batch, and review work for continuous improvement.

🌟 Ready to start? Reply ✅ to dive in!""",
        "next": "lesson_6_step_1"
    },
    "lesson_6_step_1": {
        "text": """📜 Agile methodologies were born from the Manifesto for Agile Software Development (https://agilemanifesto.org/). They emphasise:

- Individuals and interactions over processes and tools.
- Working software over comprehensive documentation.
- Customer collaboration over contract negotiation.
- Responding to change over following a plan.

✅ Task: Reflect on how these values apply to your project or work. Reply 📝 with one Agile value you want to implement.""",
        "next": "lesson_6_step_2"
    },
    "lesson_6_step_2": {
        "text": """📌 Understand your work package. Scoping defines what needs to be delivered and why.

✅ Task: Answer these questions:
1. What is to be created and delivered by completing this work?
2. What is the purpose of the work?

Reply 📝 with your answers to move forward.""",
        "next": "lesson_6_step_3"
    },
    "lesson_6_step_3": {
        "text": """🎯 Break your work into smaller, manageable parts. Milestones are clear checkpoints that show progress.

✅ Task:
1. What are the parts of the project or activities that will make it complete?
2. List them in the order they need to be done.

Reply 📝 with your milestones.""",
        "next": "lesson_6_step_4"
    },
    "lesson_6_step_4": {
        "text": """🛠️ Break milestones into actionable steps. Tasks should be specific and achievable.

✅ Task:
1. What specific tasks need to be done to achieve each milestone?
2. What resources or skills will you need to complete these tasks?

Reply 📝 with a list of tasks for your first milestone.""",
        "next": "lesson_6_step_5"
    },
    "lesson_6_step_5": {
        "text": """📋 Focus on what matters most. Task prioritisation ensures efficient progress.

✅ Task: Arrange your tasks in order of dependency:
1. Which tasks must be completed first?
2. Which tasks can be done simultaneously?

Reply 📝 with your prioritised task list.""",
    "next": "lesson_6_step_6"
    },
    "lesson_6_step_6": {
        "text": """⏳ Batch tasks into weekly sprints. Sprints help you focus on delivering results incrementally.

✅ Task:
1. Assign each task a completion time.
2. Group tasks into weekly sprints based on priority and available time.

Reply 📝 with your sprint plan for the first week.""",
        "next": "lesson_6_step_7"
    },
    "lesson_6_step_7": {
        "text": """🔄 Continuous improvement is key. At the end of each week, review your progress and plan for the next.

✅ Task: Reflect on these questions:
1. What did I complete this week?
2. What challenges or blockers did I face?
3. What can I improve next week?

Reply 📝 with your answers to close the sprint.

🌟 Congratulations! You’ve completed Lesson 6: Project Thinking. You now have a systematic way to scope, plan, and execute your work efficiently.

🚀 This concludes the course! Ready to apply what you’ve learned? Reply ✅ to share your next steps!,"""
    }

}



# Track user progress
user_data = {}

def start(update: Update, context: CallbackContext):
    """Start command handler"""
    user = update.message.from_user
    UserManager.save_user_info(user)
    
    welcome_text = """
Welcome to the Learning Bot! 🎓

Available commands:
/start - Start or restart the learning journey
/journal - View your learning journal
/feedback - Send feedback or questions to us
/help - Show this help message

Type /start to begin your learning journey!
    """
    update.message.reply_text(welcome_text)
    send_lesson(update, context, "lesson_1")



def send_lesson(update: Update, context: CallbackContext, lesson_key: str):
    """Send the lesson content."""
    # Get chat_id from either message or callback query
    if update.message:
        chat_id = update.message.chat_id
    else:
        chat_id = update.callback_query.message.chat_id
        
    lesson = lessons.get(lesson_key)
    if lesson:
        context.bot.send_message(
            chat_id=chat_id,
            text=lesson["text"],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅", callback_data=lesson["next"])]
            ]) if lesson["next"] else None
        )



def handle_response(update: Update, context: CallbackContext):
    """Handle button responses."""
    query = update.callback_query
    query.answer()  # Acknowledge the button press to remove loading state

    next_step = query.data
    if next_step and next_step in lessons:  # Check if next_step exists in lessons
        user_data[query.message.chat_id] = next_step
        send_lesson(update, context, next_step)
    else:
        query.edit_message_text(text="Please reply with your input to proceed.")



def error_handler(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    print(f'Update "{update}" caused error "{context.error}"')



def handle_message(update: Update, context: CallbackContext):
    """Handle user input and responses"""
    chat_id = update.message.chat_id
    current_step = user_data.get(chat_id)
    user_response = update.message.text

    if current_step in lessons:
        # Save the response to the user's journal
        save_journal_entry(chat_id, current_step, user_response)
        
        # Get next step from lessons dictionary
        next_step = lessons[current_step].get("next")
        if next_step:
            # Update the user's current step in `user_data`
            user_data[chat_id] = next_step

            # Send confirmation and next lesson
            context.bot.send_message(
                chat_id=chat_id,
                text="✅ Response saved! Moving to next step..."
            )
            send_lesson(update, context, next_step)
        else:
            context.bot.send_message(
                chat_id=chat_id,
                text="✅ Response saved! You've completed all lessons."
            )
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text="Please use the buttons to navigate lessons."
        )



# Add command to get journal
def get_journal(update: Update, context: CallbackContext):
    """Send user their learning journal"""
    chat_id = update.message.chat_id
    journal_file = JOURNALS_DIR / f"journal_{chat_id}.json"
    
    if journal_file.exists():
        with open(journal_file) as f:
            journal = json.load(f)
        
        # Format journal entries as text
        entries_text = "📚 Your Learning Journal:\n\n"
        for entry in journal["entries"]:
            entries_text += f"📝 {entry['lesson']}\n"
            entries_text += f"💭 Your response: {entry['response']}\n"
            entries_text += f"⏰ {entry['timestamp']}\n\n"
        
        context.bot.send_message(
            chat_id=chat_id,
            text=entries_text
        )
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text="No journal entries found yet. Complete some lessons first!"
        )



def help_command(update: Update, context: CallbackContext):
    """Send a message when the command /help is issued."""
    help_text = """
🤖 Available commands:

/start - Start or restart the learning journey
/journal - View your learning journal
/help - Show this help message

To progress through lessons:
1. Read the lesson content
2. Complete the given task
3. Send your response
4. Click ✅ when prompted to move forward

Your responses are automatically saved to your learning journal.
    """
    update.message.reply_text(help_text)

async def setup_commands(bot):
    """Set up the bot commands in the client."""
    commands = [
        BotCommand("start", "Start or restart the learning journey"),
        BotCommand("journal", "View your learning journal"),
        BotCommand("help", "Show help information")
    ]
    await bot.set_my_commands(commands)



def feedback_command(update: Update, context: CallbackContext):
    """Handle feedback command"""
    update.message.reply_text(
        "Please share your feedback or questions. Your message will be sent to our team."
    )
    context.user_data['expecting_feedback'] = True

def handle_feedback(update: Update, context: CallbackContext):
    """Handle incoming feedback"""
    if context.user_data.get('expecting_feedback'):
        FeedbackManager.save_feedback(update.message.from_user.id, update.message.text)
        update.message.reply_text(
            "Thank you for your feedback! Our team will review it. 🙏"
        )
        context.user_data['expecting_feedback'] = False
        return True
    return False

# Admin Commands
def is_admin(user_id):
    """Check if user is an admin"""
    return user_id in ADMIN_IDS

def list_users(update: Update, context: CallbackContext):
    """Admin command to list all users"""
    if not is_admin(update.message.from_user.id):
        update.message.reply_text("This command is only available to admins.")
        return

    users_list = []
    for user_file in USERS_DIR.glob("user_*.json"):
        with open(user_file) as f:
            users_list.append(json.load(f))
    
    report = "📊 Users Report:\n\n"
    for user in users_list:
        report += f"👤 User: {user['username'] or user['first_name']}\n"
        report += f"📝 Current Lesson: {user['current_lesson']}\n"
        report += f"✅ Completed: {len(user['completed_lessons'])} lessons\n\n"
    
    update.message.reply_text(report)

def view_feedback(update: Update, context: CallbackContext):
    """Admin command to view all feedback"""
    if not is_admin(update.message.from_user.id):
        update.message.reply_text("This command is only available to admins.")
        return

    feedback_list = FeedbackManager.get_all_feedback()
    report = "📬 Feedback Report:\n\n"
    for feedback in feedback_list:
        user = UserManager.get_user_info(feedback['user_id'])
        report += f"From: {user['username'] if user else 'Unknown'}\n"
        report += f"Time: {feedback['timestamp']}\n"
        report += f"Message: {feedback['feedback']}\n\n"
    
    update.message.reply_text(report)



#put Flask in a separate function
def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)



def error_handler(update: Update, context: CallbackContext):
    """Log Errors caused by Updates."""
    print(f'Update "{update}" caused error "{context.error}"')



# Set up the bot
def main():
    updater = Updater("7865567051:AAH0i08bEq_jM14doJuh2a88lkYszryBufM", use_context=True)
    dp = updater.dispatcher


    # Regular user commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("journal", get_journal))
    dp.add_handler(CommandHandler("feedback", feedback_command))
    dp.add_handler(CommandHandler("help", help_command))


    # Admin commands
    dp.add_handler(CommandHandler("users", list_users))
    dp.add_handler(CommandHandler("viewfeedback", view_feedback))


    # Message handlers
    dp.add_handler(CallbackQueryHandler(handle_response))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))


    # Set up commands in Telegram client
    updater.bot.set_my_commands([
        ("start", "Start or restart the learning journey"),
        ("journal", "View your learning journal"),
        ("feedback", "Send feedback or questions"),
        ("help", "Show help information")
    ])


    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()


    # Start the bot
    print("Bot started successfully!")
    updater.start_polling()
    updater.idle()



if __name__ == "__main__":
    main()
