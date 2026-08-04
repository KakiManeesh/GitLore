# GitLore RAG Frontend

A simple, beautiful React frontend for the GitLore RAG System.

## Setup

1. Make sure you have Node.js installed.
2. Install dependencies:
```bash
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

## Running the App

Start the development server:
```bash
npm run dev
```

## Structure
- `src/App.jsx`: Main application container.
- `src/components/QueryInput.jsx`: The search bar for entering queries.
- `src/components/AnswerDisplay.jsx`: The component that displays the generated answer, subqueries, and stats.
- `src/index.css`: Tailwind CSS imports.
