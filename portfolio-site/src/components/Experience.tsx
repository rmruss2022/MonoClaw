"use client";

import { motion } from "framer-motion";
import { Briefcase } from "lucide-react";

const experiences = [
  {
    company: "AgriVaR",
    role: "Software Engineer",
    duration: "June 2024 – Present",
    location: "Remote",
    description:
      "Big-data agricultural startup optimizing farm operations through advanced data analysis and visualization.",
    achievements: [
      "Led a ground-up AWS platform re-architecture, improving reliability and reducing on-call firefighting as product usage scaled",
      "Built fast, operator-grade React/TypeScript tooling for geospatial + time-series workflows used in day-to-day farm decisions",
      "Shipped a real-time commodity trading experience with live market streams and alerting to support faster execution",
      "Delivered precision mapping and annotation tooling that increased planning accuracy and contributed to 20%+ projected harvest gains",
    ],
    tech: ["React", "TypeScript", "AWS", "Geospatial Data", "Real-time Streaming"],
    color: "cyan",
  },
  {
    company: "BitWave",
    role: "Software Engineer II",
    duration: "June 2023 – June 2024",
    location: "Remote",
    description:
      "Digital asset platform providing financial and crypto reporting infrastructure for enterprises.",
    achievements: [
      "Owned and shipped a Rust CQRS analytics pipeline that reduced key query latency from 4s+ to sub-second",
      "Built a high-throughput Rust messaging system to support reliable event processing across distributed services",
      "Engineered multi-chain indexing across 60+ blockchains, improving reconciliation quality and customer trust in reported balances",
      "Automated Optimism token-balance deployments with chain-specific guardrails to reduce operational risk and manual intervention",
    ],
    tech: ["Rust", "CQRS Architecture", "Distributed Systems", "Blockchain/Crypto", "Cloud Deployment"],
    color: "purple",
  },
  {
    company: "Unilever | Liquid I.V.",
    role: "Full Stack Software Engineer",
    duration: "July 2021 – June 2023",
    location: "Remote",
    description:
      "Leading hydration and wellness brand, part of Unilever. Engineered enterprise software for logistics and inventory management.",
    achievements: [
      "Built a nationwide inventory intelligence platform for monitoring stock health and forecasting demand across warehouses, DCs, and retail channels",
      "Developed React/TypeScript app optimized for fast decision-making by non-technical stakeholders",
      "Designed and deployed an analytics pipeline across GraphQL, DynamoDB, Lambda, SES, and Cognito to power reliable operations reporting",
      "Created a single source of truth across email and logistics communications, improving execution alignment while gaining new operational insights for the business",
    ],
    tech: ["React", "TypeScript", "GraphQL", "AWS (Lambda, DynamoDB, SES, Cognito)", "Enterprise Architecture"],
    color: "pink",
  },
];

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.2,
    },
  },
};

const item = {
  hidden: { opacity: 0, x: -30 },
  show: { opacity: 1, x: 0 },
};

export default function Experience() {
  return (
    <section id="experience" className="relative py-20 md:py-32 overflow-hidden">
      {/* Background Accent */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-space-light/30 to-transparent pointer-events-none" />

      <div className="relative max-w-7xl mx-auto px-6 md:px-12">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-16"
        >
          <div className="font-mono text-sm mb-4" style={{ color: "var(--accent-cyan)" }}>
            {"<CAREER_PATH />"}
          </div>
          <h2 className="text-4xl md:text-6xl lg:text-7xl font-bold mb-4">
            Experience
          </h2>
          <p className="text-xl md:text-2xl" style={{ color: "var(--gray-400)" }}>
            Where I've built products that scale
          </p>
          <div
            className="h-1.5 w-40 mt-6 rounded-full"
            style={{
              background: "linear-gradient(to right, var(--accent-purple), var(--accent-pink), var(--accent-cyan))",
              boxShadow: "0 0 10px rgba(176, 38, 255, 0.5)",
            }}
          />
        </motion.div>

        {/* Timeline */}
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          className="relative"
        >
          {/* Vertical Line (hidden on mobile) */}
          <div className="absolute left-0 md:left-8 top-0 bottom-0 w-px bg-gradient-to-b from-cyan via-purple to-pink opacity-30 hidden md:block" />

          {/* Experience Cards */}
          <div className="space-y-12 md:space-y-16">
            {experiences.map((exp, index) => (
              <motion.div
                key={exp.company}
                variants={item}
                className="relative"
              >
                {/* Timeline Dot */}
                <div className="absolute left-0 md:left-8 top-8 w-4 h-4 -ml-2 rounded-full bg-gradient-to-br from-cyan to-purple shadow-[0_0_20px_rgba(0,217,255,0.5)] hidden md:block" />

                {/* Card */}
                <div className="md:ml-24 glass rounded-2xl p-6 md:p-8 border border-transparent hover:border-cyan/30 transition-all duration-500 hover:shadow-[0_0_40px_rgba(0,217,255,0.1)] group">
                  {/* Header */}
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <Briefcase
                          className="w-5 h-5"
                          style={{ color: `var(--accent-${exp.color})` }}
                        />
                        <h3 className="text-2xl md:text-3xl font-bold group-hover:text-cyan transition-colors">
                          {exp.company}
                        </h3>
                      </div>
                      <div className="space-y-1">
                        <p
                          className="font-semibold text-lg"
                          style={{ color: `var(--accent-${exp.color})` }}
                        >
                          {exp.role}
                        </p>
                        <p className="text-gray-400 text-sm font-mono">
                          {exp.duration} • {exp.location}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-gray-400 mb-6 leading-relaxed">
                    {exp.description}
                  </p>

                  {/* Achievements */}
                  <div className="space-y-3 mb-6">
                    {exp.achievements.map((achievement, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 text-gray-300"
                      >
                        <span
                          className="mt-1 flex-shrink-0"
                          style={{ color: `var(--accent-${exp.color})` }}
                        >
                          →
                        </span>
                        <span className="text-sm md:text-base leading-relaxed">
                          {achievement}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Tech Stack */}
                  <div className="flex flex-wrap gap-2">
                    {exp.tech.map((tech) => (
                      <span
                        key={tech}
                        className="px-3 py-1 text-xs font-mono bg-space-light rounded-full text-gray-300 transition-colors border"
                        style={{
                          borderColor: `rgba(var(--accent-${exp.color === "cyan" ? "0, 217, 255" : exp.color === "purple" ? "176, 38, 255" : "255, 0, 128"}, 0.2)`,
                        }}
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Education (Bonus Section) */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-16 md:ml-24"
        >
          <div className="glass rounded-2xl p-6 md:p-8 border border-purple/20">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-purple to-pink flex items-center justify-center flex-shrink-0">
                <span className="text-2xl">🎓</span>
              </div>
              <div>
                <h3 className="text-xl md:text-2xl font-bold mb-2">
                  Virginia Tech
                </h3>
                <p className="text-purple font-semibold mb-1">
                  B.S. Computer Science • B.S. Psychology
                </p>
                <p className="text-gray-400 text-sm">Blacksburg, VA</p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
