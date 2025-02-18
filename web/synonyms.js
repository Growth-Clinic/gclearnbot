// synonyms.js
export const SYNONYMS = {
    // Analysis & Understanding
    "analyze": ["examine", "study", "investigate", "assess", "evaluate", "review", "inspect", "explore", "dissect", "scrutinize"],
    "understand": ["comprehend", "grasp", "realize", "recognize", "perceive", "discern", "interpret", "appreciate", "fathom", "identify"],
    
    // Design & Creation
    "design": ["create", "develop", "build", "craft", "construct", "shape", "devise", "formulate", "conceive", "architect"],
    "prototype": ["model", "mockup", "sample", "demo", "test version", "beta", "draft", "simulation", "proof of concept"],
    
    // User Experience & Research
    "interview": ["question", "survey", "talk with", "speak to", "discuss with", "consult", "inquire", "converse", "chat", "meet"],
    "feedback": ["response", "reaction", "input", "opinion", "review", "comment", "critique", "assessment", "evaluation"],
    
    // Problem Solving
    "solution": ["answer", "resolution", "fix", "remedy", "approach", "method", "way", "strategy", "plan"],
    "improve": ["enhance", "upgrade", "optimize", "refine", "better", "advance", "develop", "progress", "strengthen"],
    
    // Business & Strategy
    "market": ["audience", "customers", "users", "demographic", "sector", "industry", "niche", "segment"],
    "strategy": ["plan", "approach", "method", "system", "framework", "process", "roadmap", "blueprint"],
    
    // Testing & Validation
    "test": ["verify", "validate", "check", "assess", "evaluate", "examine", "try out", "experiment"],
    "iterate": ["repeat", "refine", "adjust", "modify", "update", "revise", "adapt", "improve"],
    
    // User Behavior & Psychology
    "behavior": ["action", "conduct", "habit", "pattern", "practice", "routine", "tendency"],
    "emotion": ["feeling", "sentiment", "reaction", "response", "mood", "attitude", "state of mind"],
    
    // Project Management
    "milestone": ["goal", "target", "objective", "checkpoint", "achievement", "marker", "stage"],
    "task": ["activity", "action item", "assignment", "job", "work item", "deliverable"],
    
    // Collaboration & Communication
    "collaborate": ["work together", "cooperate", "partner", "team up", "join forces", "coordinate"],
    "communicate": ["convey", "express", "share", "discuss", "explain", "present", "relay"],
    
    // Implementation & Execution
    "implement": ["execute", "carry out", "perform", "accomplish", "achieve", "complete", "deliver"],
    "monitor": ["track", "observe", "follow", "watch", "check", "supervise", "measure"],
    
    // Quality & Value
    "effective": ["successful", "efficient", "productive", "valuable", "useful", "beneficial", "worthwhile"],
    "essential": ["crucial", "critical", "vital", "key", "core", "fundamental", "important", "necessary"],
    
    // Innovation & Creativity
    "innovative": ["creative", "novel", "unique", "original", "new", "groundbreaking", "inventive"],
    "brainstorm": ["ideate", "think up", "generate ideas", "conceptualize", "imagine", "envision"]
};

// Add common variations and forms
export function generateWordForms(word) {
    const forms = new Set([word]);
    
    // Add common suffixes
    if (word.endsWith('e')) {
        forms.add(word + 'd');  // save -> saved
        forms.add(word + 's');  // save -> saves
        forms.add(word + 'r');  // save -> saver
    } else {
        forms.add(word + 'ed');  // test -> tested
        forms.add(word + 'ing'); // test -> testing
        forms.add(word + 's');   // test -> tests
    }
    
    // Special cases
    if (word.endsWith('y')) {
        forms.add(word.slice(0, -1) + 'ies'); // study -> studies
        forms.add(word.slice(0, -1) + 'ied'); // study -> studied
    }
    
    return Array.from(forms);
}

// Helper function to get all related words
export function getRelatedWords(word) {
    word = word.toLowerCase();
    let related = new Set([word]);
    
    // Add synonyms
    if (SYNONYMS[word]) {
        SYNONYMS[word].forEach(synonym => related.add(synonym));
    }
    
    // Add word forms
    generateWordForms(word).forEach(form => related.add(form));
    
    return Array.from(related);
}