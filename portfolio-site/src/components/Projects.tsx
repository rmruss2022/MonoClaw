"use client";

import { motion } from "framer-motion";
import { ExternalLink, Github, Package, Activity, Brain, Heart, Network } from "lucide-react";

const projects = [
  {
    icon: Activity,
    iconColor: "cyan",
    title: "ActivityClaw",
    subtitle: "Real-time Activity Tracking for OpenClaw",
    description:
      "Production-ready OpenClaw plugin that provides real-time activity tracking and analytics. Features a React dashboard with live WebSocket updates, REST API, and comprehensive session monitoring. Built from scratch: TypeScript backend, React + Tailwind frontend, published to npm and ClawHub.",
    tech: ["TypeScript", "React", "Node.js", "WebSockets", "REST API", "npm"],
    links: {
      npm: "https://www.npmjs.com/package/@tigertroll14/activityclaw",
      github: "https://github.com/rmruss2022/ActivityClaw",
      clawhub: "https://clawhub.ai/skills/activityclaw-usage",
    },
    gradient: "from-cyan/20 to-purple/20",
  },
  {
    icon: Brain,
    iconColor: "purple",
    title: "ContextClaw",
    subtitle: "Intelligent Session Management & Context Analysis",
    description:
      "Advanced session management plugin for OpenClaw with intelligent context analysis. Provides real-time insights into AI agent behavior, session state, and conversation flow. Features automated session analysis, cost tracking, and context optimization strategies.",
    tech: [
      "TypeScript",
      "React",
      "Tailwind CSS",
      "Session Analytics",
      "AI Context",
    ],
    links: {
      npm: "https://www.npmjs.com/package/@tigertroll14/contextclaw",
      github: "https://github.com/rmruss2022/ContextClaw",
      clawhub: "https://clawhub.ai/skills/contextclaw-usage",
    },
    gradient: "from-purple/20 to-pink/20",
  },
  {
    icon: Heart,
    iconColor: "pink",
    title: "Ora Health",
    subtitle: "AI-Powered Mental Wellness Companion",
    description:
      "iOS application featuring Agentic AI with dynamic behaviors utilizing a Multi-Vector Broadcast Architecture. Delivers personalized meditations, affirmations, and mindset exercises. Powered by Eleven Labs for natural voice synthesis and LangChain for intelligent conversation flow.",
    tech: [
      "Swift",
      "iOS",
      "LangChain",
      "Eleven Labs TTS",
      "Vector Databases",
      "Agentic AI",
    ],
    features: [
      "🧠 Agentic AI with dynamic behaviors",
      "🎧 Daily personalized meditations",
      "💬 Multi-topic intelligent conversations",
      "📱 Native iOS experience",
    ],
    links: {
      status: "In Development (Mar 2025 - Present)",
    },
    gradient: "from-pink/20 to-cyan/20",
  },
  {
    icon: Network,
    iconColor: "cyan",
    title: "Multi-Agent Orchestration",
    subtitle: "Discord-Integrated AI Agent Swarms",
    description:
      "Built a production-ready multi-agent orchestration system with automatic Discord channel creation, Kanban board management, and inter-agent communication. Enables overnight autonomous software development by coordinating specialized AI agents.",
    tech: [
      "Node.js",
      "SQLite",
      "Discord API",
      "Express",
      "React",
      "Agent Architecture",
    ],
    features: [
      "🤖 Auto-spawning specialist agents",
      "📋 Kanban board automation",
      "💬 Discord-based agent communication",
      "🔄 Crash-recoverable state machine",
      "👁️ Human-in-the-loop oversight",
    ],
    links: {},
    gradient: "from-cyan/20 to-purple/20",
  },
];

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.15,
    },
  },
};

const item = {
  hidden: { opacity: 0, y: 30 },
  show: { opacity: 1, y: 0 },
};

export default function Projects() {
  return (
    <section id="projects" className="relative py-20 md:py-32">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <div className="font-mono text-sm mb-4" style={{ color: "var(--accent-cyan)" }}>
            {"<PORTFOLIO />"}
          </div>
          <h2 className="text-4xl md:text-6xl lg:text-7xl font-bold">
            Featured Work
          </h2>
          <div
            className="h-1.5 w-40 mt-6 rounded-full"
            style={{
              background: "linear-gradient(to right, var(--accent-cyan), var(--accent-purple), var(--accent-pink))",
              boxShadow: "0 0 10px rgba(0, 217, 255, 0.5)",
            }}
          />
        </motion.div>

        {/* Projects Grid */}
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-8"
        >
          {projects.map((project, index) => (
            <motion.div
              key={project.title}
              variants={item}
              className="group relative"
            >
              {/* Card */}
              <div className="relative glass rounded-2xl p-6 md:p-8 h-full border border-transparent hover:border-cyan/30 transition-all duration-500 hover:shadow-[0_0_40px_rgba(0,217,255,0.15)] tech-corners">
                {/* Gradient Overlay */}
                <div
                  className={`absolute inset-0 rounded-2xl bg-gradient-to-br ${project.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none`}
                />

                {/* Content */}
                <div className="relative z-10">
                  {/* Project Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="font-mono text-xs text-cyan/60">
                      [PROJECT_{String(index + 1).padStart(2, "0")}]
                    </div>
                    <div
                      className="w-12 h-12 rounded-lg flex items-center justify-center border transition-all duration-300 group-hover:scale-110"
                      style={{
                        background: `linear-gradient(135deg, rgba(var(${project.iconColor === "cyan" ? "0, 217, 255" : project.iconColor === "purple" ? "176, 38, 255" : "255, 0, 128"}), 0.2), rgba(var(${project.iconColor === "cyan" ? "0, 217, 255" : project.iconColor === "purple" ? "176, 38, 255" : "255, 0, 128"}), 0.1))`,
                        borderColor: `rgba(var(${project.iconColor === "cyan" ? "0, 217, 255" : project.iconColor === "purple" ? "176, 38, 255" : "255, 0, 128"}), 0.3)`,
                      }}
                    >
                      <project.icon
                        className="w-6 h-6"
                        style={{ color: `var(--accent-${project.iconColor})` }}
                      />
                    </div>
                  </div>

                  {/* Title */}
                  <h3 className="text-2xl md:text-3xl font-bold mb-2 group-hover:text-cyan transition-colors duration-300">
                    {project.title}
                  </h3>

                  {/* Subtitle */}
                  <p className="text-purple text-sm md:text-base mb-4 font-medium">
                    {project.subtitle}
                  </p>

                  {/* Description */}
                  <p className="text-gray-400 text-sm md:text-base leading-relaxed mb-6">
                    {project.description}
                  </p>

                  {/* Features (if available) */}
                  {project.features && (
                    <div className="mb-6 space-y-2">
                      {project.features.map((feature, i) => (
                        <div
                          key={i}
                          className="text-sm text-gray-300 font-mono"
                        >
                          {feature}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tech Stack */}
                  <div className="flex flex-wrap gap-2 mb-6">
                    {project.tech.map((tech) => (
                      <span
                        key={tech}
                        className="px-3 py-1 text-xs font-mono bg-space-light border border-cyan/20 rounded-full text-gray-300 hover:border-cyan/50 hover:text-cyan transition-colors"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>

                  {/* Links */}
                  <div className="flex flex-wrap gap-3">
                    {project.links.npm && (
                      <a
                        href={project.links.npm}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-4 py-2 bg-space-light border border-cyan/30 rounded-lg text-sm font-medium hover:border-cyan hover:bg-cyan/10 transition-all group/link"
                      >
                        <Package className="w-4 h-4" />
                        npm
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity" />
                      </a>
                    )}
                    {project.links.github && (
                      <a
                        href={project.links.github}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-4 py-2 bg-space-light border border-cyan/30 rounded-lg text-sm font-medium hover:border-cyan hover:bg-cyan/10 transition-all group/link"
                      >
                        <Github className="w-4 h-4" />
                        GitHub
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity" />
                      </a>
                    )}
                    {project.links.clawhub && (
                      <a
                        href={project.links.clawhub}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 px-4 py-2 bg-space-light border border-purple/30 rounded-lg text-sm font-medium hover:border-purple hover:bg-purple/10 transition-all group/link"
                      >
                        ClawHub
                        <ExternalLink className="w-3 h-3 opacity-0 group-hover/link:opacity-100 transition-opacity" />
                      </a>
                    )}
                    {project.links.status && (
                      <div className="flex items-center gap-2 px-4 py-2 bg-pink/10 border border-pink/30 rounded-lg text-sm font-medium text-pink">
                        {project.links.status}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
