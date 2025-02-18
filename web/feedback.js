import { getRelatedWords } from '/web/synonyms.js';

// Feedback rules configuration similar to feedback_config.py
const LESSON_FEEDBACK_RULES = {
    "lesson_2_step_1": {
        criteria: {
            "Interview Understanding": {
                keywords: ["interview", "user", "feel", "experience", "perspective", "need", "challenge", "struggle", "pain point", "emotion", "frustration", "satisfaction", "desire", "motivation"],
                good_feedback: "✅ Excellent job showing empathy and understanding your user's perspective!",
                bad_feedback: "⚠️ Try to dig deeper into how your user feels and their experiences.",
                extra_good_feedback: "💡 You've shown great insight into the emotional aspects of the user experience.",
                improvement_tips: "💡 Consider asking 'why' questions to understand the underlying emotions and motivations."
            },
            "Note Taking": {
                keywords: ["noted", "recorded", "captured", "wrote", "documented", "observation", "insight", "finding", "learned", "discovered"],
                good_feedback: "✅ Great job documenting your interview findings!",
                bad_feedback: "⚠️ Try to be more specific about what you learned from the interview.",
                improvement_tips: "💡 Consider noting down specific quotes or moments that stood out."
            }
        }
    },
    "lesson_2_step_2": {
        criteria: {
            "Deep Diving": {
                keywords: ["deeper", "follow up", "asked more", "why", "reason", "cause", "root cause", "underlying", "background", "context"],
                good_feedback: "✅ Excellent deep-dive into the user's responses!",
                bad_feedback: "⚠️ Try to probe deeper into the initial responses.",
                extra_good_feedback: "💡 Your follow-up questions show good investigative thinking.",
                improvement_tips: "💡 Use the 5 Whys technique to uncover root causes."
            },
            "Insight Generation": {
                keywords: ["insight", "pattern", "noticed", "discovered", "realized", "understood", "learned", "found", "interesting", "surprising"],
                good_feedback: "✅ Great insights from your follow-up questions!",
                bad_feedback: "⚠️ Try to identify patterns or surprising findings from your research.",
                improvement_tips: "💡 Look for unexpected or counter-intuitive findings in your research."
            }
        }
    },
    "lesson_2_step_3": {
        criteria: {
            "Problem Statement": {
                keywords: ["problem statement", "needs", "insights", "define", "challenge", "opportunity", "context", "situation", "current state", "pain points", "goals", "objectives"],
                good_feedback: "✅ Clear problem definition that combines user needs and insights!",
                bad_feedback: "⚠️ Make sure your problem statement includes both user needs and insights.",
                extra_good_feedback: "💡 Your problem statement effectively bridges user needs with opportunities for innovation.",
                improvement_tips: "💡 Try using the format: '[User] needs a way to [action] because [insight]'"
            },
            "Needs Analysis": {
                keywords: ["trying to", "wanted to", "needed", "attempted", "goal", "intention", "purpose", "aim", "objective", "target"],
                good_feedback: "✅ Good analysis of user needs and intentions!",
                bad_feedback: "⚠️ Try to be more specific about what the user was trying to accomplish.",
                improvement_tips: "💡 Consider both the immediate need and the broader goal."
            }
        }
    },
    "lesson_2_step_4": {
        criteria: {
            "Solution Generation": {
                keywords: ["solution", "idea", "creative", "brainstorm", "alternative", "possibility", "innovation", "concept", "approach", "strategy", "option", "proposal"],
                good_feedback: "✅ Great variety of creative solutions!",
                bad_feedback: "⚠️ Try generating more diverse ideas - think outside the box!",
                extra_good_feedback: "💡 Your ideas show excellent range and creativity in problem-solving.",
                improvement_tips: "💡 Consider combining different ideas or drawing inspiration from other fields."
            },
            "Solution Quality": {
                keywords: ["unique", "innovative", "different", "new", "original", "fresh", "novel", "unconventional", "creative", "imaginative"],
                good_feedback: "✅ Your solutions show original thinking!",
                bad_feedback: "⚠️ Try to think of more unique or unconventional solutions.",
                improvement_tips: "💡 Consider how to combine or modify existing solutions in new ways."
            }
        }
    },
    "lesson_2_step_5": {
        criteria: {
            "Prototype Creation": {
                keywords: ["prototype", "test", "mock", "sketch", "wireframe", "design", "iteration", "feedback", "user testing", "validation", "experiment", "trial"],
                good_feedback: "✅ Good job creating a testable prototype!",
                bad_feedback: "⚠️ Consider making your prototype more concrete and testable.",
                extra_good_feedback: "💡 Your prototype effectively demonstrates key features for testing.",
                improvement_tips: "💡 Think about what specific aspects you want to test with users."
            },
            "Prototype Focus": {
                keywords: ["core feature", "main function", "key aspect", "essential", "critical", "important", "primary", "fundamental", "basic"],
                good_feedback: "✅ Good focus on core functionality in your prototype!",
                bad_feedback: "⚠️ Try to focus on the most essential features first.",
                improvement_tips: "💡 Start with the minimum viable features needed to test your concept."
            }
        }
    },
    "lesson_2_step_6": {
        criteria: {
            "Feedback Collection": {
                keywords: ["feedback", "response", "reaction", "opinion", "suggestion", "comment", "input", "review", "critique", "recommendation"],
                good_feedback: "✅ Great job gathering user feedback!",
                bad_feedback: "⚠️ Try to get more specific feedback from users.",
                extra_good_feedback: "💡 You've collected valuable insights from your testing.",
                improvement_tips: "💡 Ask users about both what works and what could be improved."
            },
            "Iteration Planning": {
                keywords: ["improve", "refine", "update", "change", "modify", "adjust", "enhance", "revise", "iterate", "upgrade"],
                good_feedback: "✅ Good planning for improvements based on feedback!",
                bad_feedback: "⚠️ Consider how to incorporate the feedback into specific improvements.",
                improvement_tips: "💡 Prioritize which improvements will have the biggest impact."
            }
        }
    },
    "lesson_3_step_1": {
        criteria: {
            "Business Model Understanding": {
                keywords: ["business model", "create", "deliver", "capture", "value", "sustainable", "profit", "customer", "service", "product"],
                good_feedback: "✅ Great understanding of how to create, deliver, and capture value!",
                bad_feedback: "⚠️ Try to think more about how your idea will create and sustain value.",
                extra_good_feedback: "💡 You've clearly articulated how your business will generate value.",
                improvement_tips: "💡 Consider how your business model aligns with customer needs and market demands."
            },
            "Customer Focus": {
                keywords: ["customer", "user", "serve", "target", "audience", "segment", "demographic", "behavior"],
                good_feedback: "✅ Excellent focus on identifying your target customers!",
                bad_feedback: "⚠️ Try to be more specific about who your customers are and their needs.",
                improvement_tips: "💡 Think about the specific problems your customers are facing."
            }
        }
    },
    "lesson_3_step_2": {
        criteria: {
            "Canvas Completion": {
                keywords: ["canvas", "customer segments", "value proposition", "channels", "revenue streams", "key resources", "key activities", "key partnerships", "cost structure"],
                good_feedback: "✅ Great job mapping out your business model canvas!",
                bad_feedback: "⚠️ Try to fill in all sections of the canvas to get a complete picture.",
                extra_good_feedback: "💡 Your canvas shows a clear and comprehensive view of your business model.",
                improvement_tips: "💡 Consider how each section of the canvas interacts with the others."
            },
            "Value Proposition Clarity": {
                keywords: ["value proposition", "problem", "solution", "unique", "different", "benefit", "advantage"],
                good_feedback: "✅ Your value proposition is clear and compelling!",
                bad_feedback: "⚠️ Try to make your value proposition more specific and unique.",
                improvement_tips: "💡 Focus on what makes your solution stand out from competitors."
            }
        }
    },
    "lesson_3_step_3": {
        criteria: {
            "Model Variation": {
                keywords: ["variation", "experiment", "test", "revenue model", "channel", "partnership", "iteration"],
                good_feedback: "✅ Great job exploring different business model variations!",
                bad_feedback: "⚠️ Try to think of more creative ways to test your business model.",
                extra_good_feedback: "💡 Your variations show innovative thinking and flexibility.",
                improvement_tips: "💡 Consider how different revenue models or channels could impact your business."
            },
            "Innovation": {
                keywords: ["innovative", "creative", "unique", "unconventional", "fresh", "new", "original"],
                good_feedback: "✅ Your business model shows creative and innovative thinking!",
                bad_feedback: "⚠️ Try to think outside the box for more unique approaches.",
                improvement_tips: "💡 Look for inspiration from other industries or markets."
            }
        }
    },
    "lesson_3_step_4": {
        criteria: {
            "Assumption Testing": {
                keywords: ["test", "assumption", "validate", "feedback", "customer", "pilot", "experiment"],
                good_feedback: "✅ Great job testing your business model assumptions!",
                bad_feedback: "⚠️ Try to gather more real-world feedback to validate your model.",
                extra_good_feedback: "💡 Your testing process shows a strong focus on customer validation.",
                improvement_tips: "💡 Consider running small-scale pilots to gather more insights."
            },
            "Adaptation": {
                keywords: ["adapt", "change", "refine", "improve", "iterate", "update", "modify"],
                good_feedback: "✅ Excellent job adapting your model based on feedback!",
                bad_feedback: "⚠️ Try to make more specific changes based on your test results.",
                improvement_tips: "💡 Focus on the areas of your model that need the most refinement."
            }
        }
    },
    "lesson_3_step_5": {
        criteria: {
            "Environmental Analysis": {
                keywords: ["market", "competitor", "trend", "industry", "regulation", "technology", "economic"],
                good_feedback: "✅ Great analysis of your business environment!",
                bad_feedback: "⚠️ Try to dig deeper into the trends and forces affecting your industry.",
                extra_good_feedback: "💡 Your analysis shows a clear understanding of external factors.",
                improvement_tips: "💡 Consider how emerging technologies or regulations could impact your business."
            },
            "Opportunity Identification": {
                keywords: ["opportunity", "threat", "strength", "weakness", "adapt", "leverage", "advantage"],
                good_feedback: "✅ Excellent identification of opportunities and threats!",
                bad_feedback: "⚠️ Try to think more strategically about how to leverage opportunities.",
                improvement_tips: "💡 Focus on how your business can adapt to external changes."
            }
        }
    },
    "lesson_3_step_6": {
        criteria: {
            "Storytelling": {
                keywords: ["story", "pitch", "customer", "problem", "solution", "value", "sustain", "capture"],
                good_feedback: "✅ Great job crafting a compelling business story!",
                bad_feedback: "⚠️ Try to make your pitch more concise and focused on the customer.",
                extra_good_feedback: "💡 Your story effectively communicates the value of your business.",
                improvement_tips: "💡 Use data and examples to make your story more relatable."
            },
            "Clarity": {
                keywords: ["clear", "concise", "simple", "understand", "communicate", "explain"],
                good_feedback: "✅ Your pitch is clear and easy to understand!",
                bad_feedback: "⚠️ Try to simplify your message for better clarity.",
                improvement_tips: "💡 Focus on the key points that resonate most with your audience."
            }
        }
    },
    "lesson_4_step_1": {
        criteria: {
            "Market Understanding": {
                keywords: ["market", "customer", "segment", "target", "fit", "problem", "solution", "pain point"],
                good_feedback: "✅ Great understanding of your target market and their needs!",
                bad_feedback: "⚠️ Try to be more specific about how your product fits the market.",
                extra_good_feedback: "💡 Your analysis shows a deep understanding of customer pain points.",
                improvement_tips: "💡 Consider how your product uniquely addresses market needs."
            },
            "Problem-Solution Alignment": {
                keywords: ["problem", "solution", "align", "fit", "address", "resolve", "meet"],
                good_feedback: "✅ Excellent alignment between the problem and your solution!",
                bad_feedback: "⚠️ Try to refine how your solution directly addresses the problem.",
                improvement_tips: "💡 Focus on the specific benefits your product offers to customers."
            }
        }
    },
    "lesson_4_step_2": {
        criteria: {
            "Channel Identification": {
                keywords: ["channel", "platform", "reach", "customer", "social media", "online", "offline", "integration"],
                good_feedback: "✅ Great job identifying effective channels to reach your customers!",
                bad_feedback: "⚠️ Try to think of more channels that align with your target audience.",
                extra_good_feedback: "💡 Your channel selection shows a strong understanding of customer behavior.",
                improvement_tips: "💡 Consider how different channels can complement each other."
            },
            "Channel Alignment": {
                keywords: ["align", "fit", "customer behavior", "preference", "habit", "usage"],
                good_feedback: "✅ Excellent alignment between your channels and customer behavior!",
                bad_feedback: "⚠️ Try to ensure your channels match how your customers interact.",
                improvement_tips: "💡 Focus on channels that your customers already use regularly."
            }
        }
    },
    "lesson_4_step_3": {
        criteria: {
            "Profitability Analysis": {
                keywords: ["profit", "cost", "revenue", "CAC", "ARPU", "channel", "sustainable", "viable"],
                good_feedback: "✅ Great analysis of channel profitability!",
                bad_feedback: "⚠️ Try to calculate the costs and revenues more accurately.",
                extra_good_feedback: "💡 Your analysis shows a clear understanding of channel economics.",
                improvement_tips: "💡 Focus on channels that offer the best return on investment."
            },
            "Revenue Model Fit": {
                keywords: ["revenue model", "subscription", "one-time", "freemium", "tiered", "pricing", "align"],
                good_feedback: "✅ Excellent alignment between your revenue model and channels!",
                bad_feedback: "⚠️ Try to ensure your revenue model fits your chosen channels.",
                improvement_tips: "💡 Consider experimenting with different pricing strategies."
            }
        }
    },
    "lesson_4_step_4": {
        criteria: {
            "Market Behavior Understanding": {
                keywords: ["market", "behavior", "spending", "habit", "preference", "price", "sensitivity", "willingness"],
                good_feedback: "✅ Great understanding of your market's spending habits!",
                bad_feedback: "⚠️ Try to gather more data on how your market behaves.",
                extra_good_feedback: "💡 Your analysis shows a deep understanding of customer preferences.",
                improvement_tips: "💡 Focus on how your pricing aligns with customer expectations."
            },
            "Pricing Strategy": {
                keywords: ["pricing", "strategy", "tiered", "free trial", "experiment", "test", "feedback"],
                good_feedback: "✅ Excellent job testing and refining your pricing strategy!",
                bad_feedback: "⚠️ Try to experiment with more pricing models to find the best fit.",
                improvement_tips: "💡 Consider offering different pricing tiers to appeal to a wider audience."
            }
        }
    },
    "lesson_4_step_5": {
        criteria: {
            "Growth Plan Clarity": {
                keywords: ["growth", "plan", "strategy", "customer", "channel", "revenue", "scale", "sustainable"],
                good_feedback: "✅ Great job creating a clear and actionable growth plan!",
                bad_feedback: "⚠️ Try to make your growth plan more specific and detailed.",
                extra_good_feedback: "💡 Your growth plan shows a strong focus on scalability and sustainability.",
                improvement_tips: "💡 Focus on the key metrics that will drive your growth."
            },
            "Execution Readiness": {
                keywords: ["execute", "implement", "action", "plan", "strategy", "timeline", "resource"],
                good_feedback: "✅ Excellent preparation for executing your growth plan!",
                bad_feedback: "⚠️ Try to ensure you have the resources and timeline in place.",
                improvement_tips: "💡 Consider breaking your plan into smaller, actionable steps."
            }
        }
    },
    "lesson_5_step_1": {
        criteria: {
            "Emotional Insight": {
                keywords: ["emotion", "decision", "behavior", "trigger", "influence", "motivation", "feeling"],
                good_feedback: "✅ Great understanding of how emotions influence decisions!",
                bad_feedback: "⚠️ Try to dig deeper into the emotional triggers behind user behavior.",
                extra_good_feedback: "💡 Your analysis shows a deep understanding of emotional drivers.",
                improvement_tips: "💡 Consider how different emotions can lead to different actions."
            },
            "Personal Reflection": {
                keywords: ["reflect", "personal", "experience", "decision", "emotion", "example", "recent"],
                good_feedback: "✅ Excellent reflection on how emotions influence your own decisions!",
                bad_feedback: "⚠️ Try to provide more specific examples from your own experience.",
                improvement_tips: "💡 Think about how your emotional responses can inform product design."
            }
        }
    },
    "lesson_5_step_2": {
        criteria: {
            "Trigger Identification": {
                keywords: ["trigger", "internal", "external", "cue", "prompt", "action", "behavior"],
                good_feedback: "✅ Great job identifying triggers that drive user behavior!",
                bad_feedback: "⚠️ Try to think of more specific triggers that apply to your product.",
                extra_good_feedback: "💡 Your analysis shows a clear understanding of user triggers.",
                improvement_tips: "💡 Consider how different triggers can lead to different actions."
            },
            "Action Analysis": {
                keywords: ["action", "behavior", "simple", "reward", "anticipation", "motivation", "ability"],
                good_feedback: "✅ Excellent analysis of the actions users take!",
                bad_feedback: "⚠️ Try to focus on the simplest actions users can take to get a reward.",
                improvement_tips: "💡 Think about how to make actions as easy as possible for users."
            }
        }
    },
    "lesson_5_step_3": {
        criteria: {
            "Internal Trigger Application": {
                keywords: ["internal", "trigger", "emotion", "situation", "boredom", "loneliness", "stress"],
                good_feedback: "✅ Great job applying internal triggers to your product!",
                bad_feedback: "⚠️ Try to think of more specific emotions or situations that trigger usage.",
                extra_good_feedback: "💡 Your application of internal triggers is well thought out.",
                improvement_tips: "💡 Consider how different emotions can lead to different user actions."
            },
            "Reward Design": {
                keywords: ["reward", "variable", "social", "hunt", "self", "satisfaction", "accomplishment"],
                good_feedback: "✅ Excellent design of variable rewards for your product!",
                bad_feedback: "⚠️ Try to think of more creative or unexpected rewards.",
                improvement_tips: "💡 Focus on rewards that keep users engaged over time."
            }
        }
    },
    "lesson_5_step_4": {
        criteria: {
            "Case Study Analysis": {
                keywords: ["case study", "Alexa", "trigger", "action", "reward", "investment", "habit"],
                good_feedback: "✅ Great analysis of how Alexa uses the Hooked Model!",
                bad_feedback: "⚠️ Try to think of more specific tactics Alexa uses to drive engagement.",
                extra_good_feedback: "💡 Your analysis shows a deep understanding of habit-forming design.",
                improvement_tips: "💡 Consider how you can apply similar tactics to your product."
            },
            "Tactic Application": {
                keywords: ["apply", "tactic", "trigger", "action", "reward", "investment", "habit"],
                good_feedback: "✅ Excellent job applying Alexa's tactics to your product!",
                bad_feedback: "⚠️ Try to think of more creative ways to apply these tactics.",
                improvement_tips: "💡 Focus on how to make your product more habit-forming."
            }
        }
    },
    "lesson_5_step_5": {
        criteria: {
            "Behavior Model Understanding": {
                keywords: ["behavior", "model", "motivation", "ability", "trigger", "Fogg", "action"],
                good_feedback: "✅ Great understanding of behavior models and how they influence actions!",
                bad_feedback: "⚠️ Try to think more about how motivation and ability interact.",
                extra_good_feedback: "💡 Your analysis shows a clear understanding of behavior design.",
                improvement_tips: "💡 Consider how to increase user motivation or simplify actions."
            },
            "Product Application": {
                keywords: ["apply", "product", "motivation", "ability", "trigger", "action", "simplify"],
                good_feedback: "✅ Excellent job applying behavior models to your product!",
                bad_feedback: "⚠️ Try to think of more ways to increase user motivation or ability.",
                improvement_tips: "💡 Focus on making the desired actions as easy as possible."
            }
        }
    },
    "lesson_6_step_1": {
        criteria: {
            "Agile Value Understanding": {
                keywords: ["agile", "value", "individual", "interaction", "software", "collaboration", "change"],
                good_feedback: "✅ Great understanding of Agile values and principles!",
                bad_feedback: "⚠️ Try to think more about how Agile values apply to your project.",
                extra_good_feedback: "💡 Your reflection shows a strong alignment with Agile principles.",
                improvement_tips: "💡 Consider how to prioritize collaboration and adaptability."
            },
            "Value Application": {
                keywords: ["apply", "value", "agile", "project", "work", "team", "collaboration"],
                good_feedback: "✅ Excellent job applying Agile values to your project!",
                bad_feedback: "⚠️ Try to think of more specific ways to implement Agile values.",
                improvement_tips: "💡 Focus on how to foster collaboration and respond to change."
            }
        }
    },
    "lesson_6_step_2": {
        criteria: {
            "Scope Clarity": {
                keywords: ["scope", "work", "deliver", "purpose", "goal", "objective", "define"],
                good_feedback: "✅ Great job defining the scope and purpose of your work!",
                bad_feedback: "⚠️ Try to be more specific about what needs to be delivered.",
                extra_good_feedback: "💡 Your scope is clear and well-defined.",
                improvement_tips: "💡 Consider breaking down the scope into smaller, manageable parts."
            },
            "Purpose Alignment": {
                keywords: ["purpose", "align", "goal", "objective", "target", "outcome"],
                good_feedback: "✅ Excellent alignment between your work and its purpose!",
                bad_feedback: "⚠️ Try to ensure your work directly supports your goals.",
                improvement_tips: "💡 Focus on how each task contributes to the overall objective."
            }
        }
    },
    "lesson_6_step_3": {
        criteria: {
            "Milestone Definition": {
                keywords: ["milestone", "checkpoint", "progress", "task", "activity", "complete", "order"],
                good_feedback: "✅ Great job defining clear milestones for your project!",
                bad_feedback: "⚠️ Try to break your work into smaller, more manageable milestones.",
                extra_good_feedback: "💡 Your milestones are well-structured and achievable.",
                improvement_tips: "💡 Consider how each milestone contributes to the overall project."
            },
            "Task Sequencing": {
                keywords: ["sequence", "order", "dependency", "task", "milestone", "complete"],
                good_feedback: "✅ Excellent sequencing of tasks and milestones!",
                bad_feedback: "⚠️ Try to ensure tasks are ordered based on dependencies.",
                improvement_tips: "💡 Focus on completing tasks that are prerequisites for others."
            }
        }
    },
    "lesson_6_step_4": {
        criteria: {
            "Task Specificity": {
                keywords: ["task", "specific", "actionable", "achievable", "resource", "skill", "complete"],
                good_feedback: "✅ Great job defining specific and actionable tasks!",
                bad_feedback: "⚠️ Try to make your tasks more specific and achievable.",
                extra_good_feedback: "💡 Your tasks are well-defined and actionable.",
                improvement_tips: "💡 Consider breaking down tasks into smaller steps if needed."
            },
            "Resource Planning": {
                keywords: ["resource", "skill", "need", "complete", "task", "milestone", "plan"],
                good_feedback: "✅ Excellent planning of resources and skills needed!",
                bad_feedback: "⚠️ Try to ensure you have all the resources and skills required.",
                improvement_tips: "💡 Focus on identifying any gaps in resources or skills."
            }
        }
    },
    "lesson_6_step_5": {
        criteria: {
            "Task Prioritization": {
                keywords: ["prioritize", "task", "order", "dependency", "important", "urgent", "complete"],
                good_feedback: "✅ Great job prioritizing tasks based on importance and dependencies!",
                bad_feedback: "⚠️ Try to ensure tasks are prioritized based on their impact.",
                extra_good_feedback: "💡 Your task prioritization shows a clear focus on what matters most.",
                improvement_tips: "💡 Consider how to balance urgent tasks with important ones."
            },
            "Dependency Management": {
                keywords: ["dependency", "task", "order", "complete", "sequence", "priority"],
                good_feedback: "✅ Excellent management of task dependencies!",
                bad_feedback: "⚠️ Try to ensure tasks are ordered based on their dependencies.",
                improvement_tips: "💡 Focus on completing tasks that are prerequisites for others."
            }
        }
    },
    "lesson_6_step_6": {
        criteria: {
            "Sprint Planning": {
                keywords: ["sprint", "plan", "task", "week", "time", "complete", "priority"],
                good_feedback: "✅ Great job planning your sprints and assigning tasks!",
                bad_feedback: "⚠️ Try to ensure your sprints are realistic and achievable.",
                extra_good_feedback: "💡 Your sprint plan is well-structured and focused.",
                improvement_tips: "💡 Consider how to balance workload across sprints."
            },
            "Time Management": {
                keywords: ["time", "manage", "sprint", "task", "complete", "priority", "schedule"],
                good_feedback: "✅ Excellent time management in your sprint planning!",
                bad_feedback: "⚠️ Try to ensure tasks are allocated based on available time.",
                improvement_tips: "💡 Focus on setting realistic deadlines for each task."
            }
        }
    },
    "lesson_6_step_7": {
        criteria: {
            "Progress Review": {
                keywords: ["review", "progress", "complete", "task", "sprint", "week", "achievement"],
                good_feedback: "✅ Great job reviewing your progress and achievements!",
                bad_feedback: "⚠️ Try to be more specific about what was completed and what wasn't.",
                extra_good_feedback: "💡 Your review shows a clear understanding of your progress.",
                improvement_tips: "💡 Consider how to address any challenges or blockers."
            },
            "Reflection and Improvement": {
                keywords: ["reflect", "improve", "challenge", "blocker", "next", "week", "plan"],
                good_feedback: "✅ Excellent reflection on challenges and planning for improvement!",
                bad_feedback: "⚠️ Try to think of more specific ways to improve next week.",
                improvement_tips: "💡 Focus on actionable steps to overcome challenges."
            }
        }
    }
};

class WebFeedbackAnalyzer {
    constructor() {
        this.rules = LESSON_FEEDBACK_RULES;
    }

    // Enhanced method to find the correct lesson rule
    _findLessonRule(lessonId) {
        console.log('Finding rule for:', lessonId);
        
        // If direct match exists, return it
        if (this.rules[lessonId]) {
            return this.rules[lessonId];
        }
    
        // Try to match the base lesson to its first step
        const baseMatch = lessonId.match(/^(lesson_\d+)$/);
        if (baseMatch) {
            const firstStepRule = `${baseMatch[1]}_step_1`;
            console.log('Attempting to match first step:', firstStepRule);
            return this.rules[firstStepRule];
        }
    
        // Try matching main lesson steps
        const stepMatch = Object.keys(this.rules).find(ruleKey => 
            ruleKey.startsWith(lessonId + '_step_')
        );
    
        console.log('Matched step rule:', stepMatch);
        return stepMatch ? this.rules[stepMatch] : null;
    }

    // Enhanced keyword matching
    _matchKeyword(text, keyword) {
        // Convert text and keyword to lowercase for consistency
        text = text.toLowerCase();
        keyword = keyword.toLowerCase();
    
        // Use the lemmatizer to get the base form of the keyword
        const lemmatizedKeyword = lemmatize(keyword);
        // Split the response into words and lemmatize each one
        const lemmatizedWords = text.split(/\s+/).map(word => lemmatize(word));
    
        // Handle multi-word phrases
        if (keyword.includes(' ')) {
            // Lemmatize each word in the phrase and rejoin them
            const lemmatizedPhrase = keyword.split(' ').map(w => lemmatize(w)).join(' ');
            const phraseRegex = new RegExp(`\\b${lemmatizedPhrase}\\b`, 'i');
            if (phraseRegex.test(text)) {
                console.log(`Multi-word phrase match found for "${keyword}"`);
                return true;
            }
        } else {
            // For single words, check if the lemmatized keyword is present in the lemmatized words of the text
            if (lemmatizedWords.includes(lemmatizedKeyword)) {
                console.log(`Lemmatized match found for "${keyword}" as "${lemmatizedKeyword}"`);
                return true;
            }
        }
    
        // Optionally, also check using your synonyms function if you still want that extra layer.
        const relatedWords = getRelatedWords(keyword);  // your existing function
        const lemmatizedRelated = relatedWords.map(word => lemmatize(word));
        if (lemmatizedRelated.some(relWord => lemmatizedWords.includes(relWord))) {
            console.log(`Related word match found for "${keyword}"`);
            return true;
        }
    
        return false;
    }    

    // Extract keywords from response
    extractKeywords(response, lessonId) {
        console.log('Extracting keywords for lesson:', lessonId);
        const lessonRule = this._findLessonRule(lessonId);
        
        if (!lessonRule) {
            console.warn(`No rules found for lesson: ${lessonId}`);
            return [];
        }
        
        const criteria = lessonRule.criteria;
        const foundKeywords = new Set();
        
        Object.values(criteria).forEach(rule => {
            rule.keywords.forEach(keyword => {
                if (this._matchKeyword(response, keyword)) {
                    console.log(`Matched keyword: ${keyword}`);
                    foundKeywords.add(keyword);
                }
            });
        });
        
        const keywordsArray = Array.from(foundKeywords);
        console.log('Found keywords:', keywordsArray);
        return keywordsArray;
    }

    // Analyze response quality
    analyzeResponseQuality(response) {
        return {
            length: response.length,
            word_count: response.split(/\s+/).length,
            sentence_count: response.split(/[.!?]+/).filter(s => s.trim()).length,
            has_punctuation: /[.!?]/.test(response),
            includes_details: response.split(/\s+/).length > 30
        };
    }

    // Generate feedback based on rules
    generateFeedback(response, lessonId) {
        console.log('Generating feedback for:', lessonId);
        
        // Find the correct lesson rule
        const lessonRule = this._findLessonRule(lessonId);
        
        if (!lessonRule) {
            console.warn(`No rules found for lesson: ${lessonId}`);
            return {
                feedback: ["Thank you for your response!"],
                keywords_found: [],
                quality_metrics: this.analyzeResponseQuality(response)
            };
        }

        const foundKeywords = this.extractKeywords(response, lessonId);
        const criteria = lessonRule.criteria;
        const feedback = [];
        let meetsExpectations = true;

        // Check each criterion
        Object.entries(criteria).forEach(([criterion, rule]) => {
            const matchCount = rule.keywords.filter(keyword => 
                foundKeywords.includes(keyword.toLowerCase())
            ).length;

            const threshold = Math.ceil(rule.keywords.length * 0.3); // 30% threshold
            
            if (matchCount >= threshold) {
                feedback.push(rule.good_feedback);
                if (rule.extra_good_feedback) {
                    feedback.push(rule.extra_good_feedback);
                }
            } else {
                meetsExpectations = false;
                feedback.push(rule.bad_feedback);
                if (rule.improvement_tips) {
                    feedback.push(rule.improvement_tips);
                }
            }
        });

        // Add quality-based feedback
        const quality = this.analyzeResponseQuality(response);
        if (quality.word_count >= 50) {
            feedback.push("✨ Excellent detail in your response!");
        } else if (quality.word_count < 20) {
            feedback.push("💡 Consider providing more details in your response.");
        }

        console.log('Generated feedback:', feedback);
        console.log('Found keywords:', foundKeywords);

        return {
            feedback,
            meetsExpectations,
            quality_metrics: quality,
            keywords_found: foundKeywords
        };
    }

    // Format feedback for display
    formatFeedbackForDisplay(feedbackResult) {
        const { feedback, quality_metrics, meetsExpectations } = feedbackResult;
        
        return {
            success_points: feedback.filter(f => f.startsWith("✅")),
            improvement_points: feedback.filter(f => f.startsWith("⚠️") || f.startsWith("💡")),
            engagement_score: this.calculateEngagementScore(quality_metrics, meetsExpectations)
        };
    }

    // Calculate engagement score based on metrics
    calculateEngagementScore(metrics, meetsExpectations) {
        let score = 0;
        
        // Word count score (up to 40 points)
        score += Math.min(metrics.word_count / 125 * 40, 40);
        
        // Sentence structure score (up to 30 points)
        if (metrics.has_punctuation) score += 15;
        if (metrics.includes_details) score += 15;
        
        // Meeting expectations score (up to 30 points)
        if (meetsExpectations) score += 30;
        
        return Math.round(score);
    }
}

function lemmatize(word) {
    word = word.toLowerCase();

    // Irregular verb forms
    const irregularVerbs = {
        "am": "be", "is": "be", "are": "be", "was": "be", "were": "be",
        "has": "have", "had": "have",
        "does": "do", "did": "do",
        "goes": "go", "went": "go",
        "comes": "come", "came": "come",
        "becomes": "become", "became": "become",
        "felt": "feel", "kept": "keep", "left": "leave", "made": "make",
        "saw": "see", "thought": "think", "took": "take", "told": "tell",
        "bought": "buy", "caught": "catch", "taught": "teach", "built": "build",
        "wrote": "write", "spoken": "speak", "spoke": "speak", "driven": "drive", "drove": "drive",
        "eaten": "eat", "ate": "eat", "fallen": "fall", "fell": "fall",
        "given": "give", "gave": "give", "known": "know", "knew": "know",
        "seen": "see", "shown": "show", "showed": "show",
        "written": "write", "ran": "run", "swam": "swim", "swum": "swim",
        "sung": "sing", "sang": "sing", "drunk": "drink", "drank": "drink"
    };
    if (irregularVerbs[word]) return irregularVerbs[word];

    // Modal auxiliary verbs → Convert to root verb
    const modals = {
        "would": "will", "should": "shall", "could": "can", "might": "may", "must": "must"
    };
    if (modals[word]) return modals[word];

    // Plural nouns to singular
    if (word.endsWith("ies") && word.length > 4) return word.slice(0, -3) + "y";  // "stories" → "story"
    if (word.endsWith("ves") && word.length > 4) return word.slice(0, -3) + "f";  // "leaves" → "leaf"
    if (word.endsWith("es") && word.length > 4 && !word.endsWith("ss")) return word.slice(0, -2); // "wishes" → "wish"
    if (word.endsWith("s") && word.length > 3 && !word.endsWith("ss")) return word.slice(0, -1); // "dogs" → "dog"

    // Progressive & participle forms
    if (word.endsWith("ing") && word.length > 5) return word.slice(0, -3);  // "running" → "run"
    if (word.endsWith("ed") && word.length > 4) return word.slice(0, -2);   // "walked" → "walk"
    if (word.endsWith("ied") && word.length > 4) return word.slice(0, -3) + "y";  // "studied" → "study"

    // Handle words ending in "ying" (e.g., "studying" → "study")
    if (word.endsWith("ying") && word.length > 5) return word.slice(0, -4) + "ie";

    // Perfect tense and passive voice handling (e.g., "been" → "be")
    const perfectTense = {
        "been": "be", "gone": "go", "done": "do"
    };
    if (perfectTense[word]) return perfectTense[word];

    return word;  // Default return if no rules apply
}

// Export for use in app.js
export const webFeedbackAnalyzer = new WebFeedbackAnalyzer();