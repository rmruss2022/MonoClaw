"use client";

import { motion } from "framer-motion";
import {
  Code2,
  Palette,
  Server,
  Database,
  Cloud,
  BrainCircuit,
  Link2,
  Sparkles,
} from "lucide-react";

const skillCategories = [
  {
    title: "Languages",
    icon: Code2,
    color: "cyan",
    skills: [
      "TypeScript",
      "Python",
      "JavaScript",
      "Rust",
      "Solidity",
      "Scala",
      "Java",
      "Swift",
      "C",
    ],
  },
  {
    title: "Frontend",
    icon: Palette,
    color: "purple",
    skills: [
      "React",
      "TypeScript",
      "HTML/CSS",
      "Responsive Design",
      "iOS Development (Swift)",
    ],
  },
  {
    title: "Backend",
    icon: Server,
    color: "pink",
    skills: ["Node.js", "Django", "Express.js", "Rust", "GraphQL", "REST APIs"],
  },
  {
    title: "Databases",
    icon: Database,
    color: "cyan",
    skills: ["PostgreSQL", "DynamoDB", "Vector Databases", "Redis"],
  },
  {
    title: "Cloud & DevOps",
    icon: Cloud,
    color: "purple",
    skills: [
      "AWS (Lambda, DynamoDB, SES, Cognito, EC2)",
      "Google Cloud",
      "Docker",
      "CI/CD",
    ],
  },
  {
    title: "AI & Machine Learning",
    icon: BrainCircuit,
    color: "pink",
    skills: [
      "PyTorch",
      "LangChain",
      "Vector Databases",
      "OpenClaw",
      "Agentic AI",
      "LLM Integration",
    ],
  },
  {
    title: "Blockchain & Web3",
    icon: Link2,
    color: "cyan",
    skills: ["Solidity", "Multi-chain Indexing", "Blockchain Infrastructure"],
  },
  {
    title: "Specialties",
    icon: Sparkles,
    color: "purple",
    skills: [
      "AI-powered automation & agent orchestration",
      "Systems architecture & scalability",
      "Developer tools & plugins",
      "Performance optimization",
      "Full-stack development (0 to production)",
      "Real-time data visualization",
    ],
  },
];

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
};

const item = {
  hidden: { opacity: 0, scale: 0.8 },
  show: { opacity: 1, scale: 1 },
};

export default function Skills() {
  return (
    <section id="skills" className="relative py-20 md:py-32">
      <div className="max-w-7xl mx-auto px-6 md:px-12">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16 text-center"
        >
          <div className="font-mono text-sm mb-4" style={{ color: "var(--accent-cyan)" }}>
            {"<TECH_STACK />"}
          </div>
          <h2 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-4">
            Technical Skills
          </h2>
          <p className="text-xl md:text-2xl" style={{ color: "var(--gray-400)" }}>
            Tools I use to build
          </p>
          <div
            className="h-1.5 w-40 mt-6 rounded-full mx-auto"
            style={{
              background: "linear-gradient(to right, var(--accent-pink), var(--accent-purple), var(--accent-cyan))",
              boxShadow: "0 0 10px rgba(255, 0, 128, 0.5)",
            }}
          />
        </motion.div>

        {/* Skills Grid */}
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
        >
          {skillCategories.map((category) => {
            const Icon = category.icon;
            return (
              <motion.div
                key={category.title}
                variants={item}
                className="group"
              >
                <div className="glass rounded-2xl p-6 border border-transparent hover:border-cyan/30 transition-all duration-500 hover:shadow-[0_0_30px_rgba(0,217,255,0.1)] h-full">
                  {/* Category Header */}
                  <div className="flex items-center gap-3 mb-6">
                    <div
                      className="w-10 h-10 rounded-lg border flex items-center justify-center group-hover:scale-110 transition-transform"
                      style={{
                        background: `linear-gradient(135deg, rgba(var(${category.color === "cyan" ? "--accent-cyan" : category.color === "purple" ? "--accent-purple" : "--accent-pink"}), 0.2), rgba(var(${category.color === "cyan" ? "--accent-cyan" : category.color === "purple" ? "--accent-purple" : "--accent-pink"}), 0.1))`,
                        borderColor: `rgba(var(${category.color === "cyan" ? "0, 217, 255" : category.color === "purple" ? "176, 38, 255" : "255, 0, 128"}), 0.3)`,
                      }}
                    >
                      <Icon
                        className="w-5 h-5"
                        style={{ color: `var(--accent-${category.color})` }}
                      />
                    </div>
                    <h3 className="text-xl font-bold group-hover:text-cyan transition-colors">
                      {category.title}
                    </h3>
                  </div>

                  {/* Skills */}
                  <div className="space-y-2">
                    {category.skills.map((skill) => (
                      <div
                        key={skill}
                        className="flex items-center gap-2 text-gray-300 text-sm group/skill"
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full flex-shrink-0 group-hover/skill:scale-150 transition-transform"
                          style={{
                            backgroundColor: `var(--accent-${category.color})`,
                          }}
                        />
                        <span className="group-hover/skill:text-cyan transition-colors">
                          {skill}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-6"
        >
          {[
            { label: "Years Coding", value: "5+" },
            { label: "Technologies", value: "20+" },
            { label: "Production Apps", value: "15+" },
            { label: "npm Packages", value: "2" },
          ].map((stat, index) => (
            <div
              key={stat.label}
              className="glass rounded-xl p-6 text-center border border-transparent hover:border-cyan/30 transition-all duration-500"
            >
              <div className="text-3xl md:text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan via-purple to-pink mb-2">
                {stat.value}
              </div>
              <div className="text-sm text-gray-400 font-mono">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
