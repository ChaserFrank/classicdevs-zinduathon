import React, { useState } from 'react'

// Mock data – replace with real API calls
const STATS = [
  { label: 'Candidates Viewed', value: '128', change: '+18 this week' },
  { label: 'Shortlisted', value: '24', change: '+5 this week' },
  { label: 'Skill Cards Explored', value: '312', change: '+42 this week' },
  { label: 'Messages Sent', value: '9', change: '3 pending replies' },
]

const FEATURED_CARDS = [
  {
    id: 1,
    title: 'Advanced React Patterns',
    owner: 'Sarah Chen',
    role: 'Frontend Engineer',
    claims: 14,
    verified: 12,
    skills: ['React', 'TypeScript', 'Performance'],
    experience: '4 years',
    location: 'Remote',
  },
  {
    id: 2,
    title: 'Node.js Microservices',
    owner: 'Marcus Rivera',
    role: 'Backend Engineer',
    claims: 11,
    verified: 9,
    skills: ['Node.js', 'Docker', 'PostgreSQL'],
    experience: '6 years',
    location: 'New York',
  },
  {
    id: 3,
    title: 'System Design & Architecture',
    owner: 'Aisha Patel',
    role: 'Senior Engineer',
    claims: 18,
    verified: 16,
    skills: ['System Design', 'AWS', 'Kafka'],
    experience: '8 years',
    location: 'Remote',
  },
  {
    id: 4,
    title: 'TypeScript & Clean Code',
    owner: 'Lena Okonkwo',
    role: 'Full-Stack Developer',
    claims: 9,
    verified: 8,
    skills: ['TypeScript', 'Next.js', 'Testing'],
    experience: '3 years',
    location: 'London',
  },
]

const SHORTLIST = [
  { id: 1, name: 'Sarah Chen', title: 'Advanced React Patterns', date: '2 days ago' },
  { id: 2, name: 'Marcus Rivera', title: 'Node.js Microservices', date: '5 days ago' },
  { id: 3, name: 'Aisha Patel', title: 'System Design & Architecture', date: '1 week ago' },
]

function RecruiterPage({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('discover')
  const [search, setSearch] = useState('')
  const [skillFilter, setSkillFilter] = useState('All')

  const skills = ['All', 'React', 'TypeScript', 'Node.js', 'System Design', 'AWS', 'Docker']

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-purple-600 flex items-center justify-center text-white font-bold text-sm">
              SP
            </div>
            <div>
              <p className="font-semibold text-sm">SkillProof</p>
              <p className="text-xs text-slate-500">Recruiter Hub</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {[
            { id: 'discover', label: 'Discover Talent', icon: '🔍' },
            { id: 'shortlist', label: 'Shortlist', icon: '⭐' },
            { id: 'messages', label: 'Messages', icon: '💬' },
            { id: 'saved-searches', label: 'Saved Searches', icon: '📌' },
            { id: 'analytics', label: 'Analytics', icon: '📈' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === item.id
                  ? 'bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
              }`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-9 w-9 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center text-sm font-medium text-purple-700 dark:text-purple-300">
              {user?.name?.[0] || 'R'}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{user?.name || 'Recruiter'}</p>
              <p className="text-xs text-slate-500 truncate">{user?.email || 'recruiter@company.com'}</p>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full text-left text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 font-medium"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between px-6 gap-4">
          <div className="relative flex-1 max-w-xl">
            <input
              type="search"
              placeholder="Search by skill, name, or card title…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-10 pr-4 text-sm focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 dark:border-slate-700 dark:bg-slate-800"
            />
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">🔍</span>
          </div>

          <div className="flex items-center gap-3">
            <button className="relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
              <span className="text-lg">🔔</span>
              <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500"></span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          {/* Discover Tab */}
          {activeTab === 'discover' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Discover Talent</h1>
                <p className="mt-1 text-slate-500">
                  Find developers through verified skill cards and real code claims
                </p>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                {STATS.map((stat) => (
                  <div
                    key={stat.label}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
                  >
                    <p className="text-sm font-medium text-slate-500">{stat.label}</p>
                    <p className="mt-2 text-3xl font-bold tracking-tight">{stat.value}</p>
                    <p className="mt-1 text-sm text-slate-500">{stat.change}</p>
                  </div>
                ))}
              </div>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-500 mr-1">Filter by skill:</span>
                {skills.map((skill) => (
                  <button
                    key={skill}
                    onClick={() => setSkillFilter(skill)}
                    className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                      skillFilter === skill
                        ? 'bg-purple-600 text-white'
                        : 'bg-white border border-slate-300 text-slate-600 hover:border-purple-400 dark:bg-slate-900 dark:border-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {skill}
                  </button>
                ))}
              </div>

              {/* Skill Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {FEATURED_CARDS.map((card) => (
                  <div
                    key={card.id}
                    className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md transition dark:border-slate-800 dark:bg-slate-900"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-lg leading-tight">{card.title}</h3>
                        <p className="mt-1 text-sm text-slate-500">
                          {card.owner} · {card.role}
                        </p>
                      </div>
                      <button className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">
                        + Shortlist
                      </button>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {card.skills.map((skill) => (
                        <span
                          key={skill}
                          className="rounded-full bg-purple-50 px-2.5 py-0.5 text-xs font-medium text-purple-700 dark:bg-purple-950/50 dark:text-purple-300"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>

                    <div className="mt-4 flex items-center gap-4 text-sm text-slate-500">
                      <span>
                        <span className="font-medium text-slate-700 dark:text-slate-300">{card.verified}</span>/{card.claims} verified claims
                      </span>
                      <span>·</span>
                      <span>{card.experience}</span>
                      <span>·</span>
                      <span>{card.location}</span>
                    </div>

                    <div className="mt-5 flex gap-2">
                      <button className="flex-1 rounded-xl bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-purple-700 transition">
                        View Card
                      </button>
                      <button className="rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800">
                        Message
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Shortlist Tab */}
          {activeTab === 'shortlist' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Your Shortlist</h1>
                <p className="mt-1 text-slate-500">Candidates you’ve saved for further review</p>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm dark:border-slate-800 dark:bg-slate-900">
                {SHORTLIST.length === 0 ? (
                  <div className="py-16 text-center text-slate-400">
                    <p className="text-lg">No candidates shortlisted yet</p>
                    <p className="mt-1 text-sm">Start exploring skill cards to build your list</p>
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800">
                    {SHORTLIST.map((item) => (
                      <div
                        key={item.id}
                        className="flex items-center justify-between px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                      >
                        <div>
                          <p className="font-medium">{item.name}</p>
                          <p className="text-sm text-slate-500">{item.title}</p>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-sm text-slate-400">{item.date}</span>
                          <button className="text-sm font-medium text-purple-600 hover:underline">
                            View
                          </button>
                          <button className="text-sm font-medium text-red-500 hover:underline">
                            Remove
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Placeholder tabs */}
          {['messages', 'saved-searches', 'analytics'].includes(activeTab) && (
            <div className="flex flex-col items-center justify-center h-72 text-slate-400">
              <p className="text-lg font-medium capitalize">{activeTab.replace('-', ' ')}</p>
              <p className="mt-1 text-sm">This section is coming soon</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default RecruiterPage