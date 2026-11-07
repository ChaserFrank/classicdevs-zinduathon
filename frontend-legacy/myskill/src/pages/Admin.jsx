import React, { useState } from 'react'

// Mock data – replace with real API calls later
const STATS = [
  { label: 'Total Users', value: '2,847', change: '+12%', positive: true },
  { label: 'Skill Cards', value: '9,431', change: '+8%', positive: true },
  { label: 'Pending Review', value: '47', change: '-3%', positive: false },
  { label: 'Active Recruiters', value: '312', change: '+5%', positive: true },
]

const RECENT_CARDS = [
  { id: 1, title: 'Advanced React Patterns', owner: 'sarah.dev', status: 'approved', claims: 14, date: '2h ago' },
  { id: 2, title: 'Node.js Microservices', owner: 'mike.codes', status: 'pending', claims: 9, date: '5h ago' },
  { id: 3, title: 'TypeScript Mastery', owner: 'lena.ts', status: 'approved', claims: 21, date: '1d ago' },
  { id: 4, title: 'System Design 101', owner: 'alex.sys', status: 'flagged', claims: 6, date: '1d ago' },
  { id: 5, title: 'GraphQL Best Practices', owner: 'priya.gql', status: 'pending', claims: 11, date: '2d ago' },
]

const RECENT_USERS = [
  { id: 1, name: 'Jordan Lee', email: 'jordan@example.com', role: 'user', joined: 'Today', cards: 3 },
  { id: 2, name: 'Aisha Khan', email: 'aisha@talent.co', role: 'recruiter', joined: 'Yesterday', cards: 0 },
  { id: 3, name: 'Chris Patel', email: 'chris@dev.io', role: 'user', joined: '2 days ago', cards: 7 },
  { id: 4, name: 'Maya Okonkwo', email: 'maya@hire.me', role: 'recruiter', joined: '3 days ago', cards: 0 },
]

function Admin({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [search, setSearch] = useState('')

  const statusStyles = {
    approved: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
    pending: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
    flagged: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  }

  const roleStyles = {
    user: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
    recruiter: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
    admin: 'bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-200',
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-sm">
              SP
            </div>
            <div>
              <p className="font-semibold text-sm">SkillProof</p>
              <p className="text-xs text-slate-500">Admin Panel</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {[
            { id: 'overview', label: 'Overview', icon: '📊' },
            { id: 'cards', label: 'Skill Cards', icon: '🃏' },
            { id: 'users', label: 'Users', icon: '👥' },
            { id: 'recruiters', label: 'Recruiters', icon: '🔍' },
            { id: 'reports', label: 'Reports', icon: '📈' },
            { id: 'settings', label: 'Settings', icon: '⚙️' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                activeTab === item.id
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300'
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
            <div className="h-9 w-9 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-sm font-medium">
              {user?.name?.[0] || 'A'}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{user?.name || 'Admin'}</p>
              <p className="text-xs text-slate-500 truncate">{user?.email || 'admin@skillproof.io'}</p>
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
        <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between px-6">
          <div className="relative w-full max-w-md">
            <input
              type="search"
              placeholder="Search users, cards, claims…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2 pl-10 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-800"
            />
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">🔍</span>
          </div>

          <div className="flex items-center gap-4">
            <button className="relative p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
              <span className="text-lg">🔔</span>
              <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-red-500"></span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Dashboard Overview</h1>
                <p className="mt-1 text-slate-500">Monitor platform health and skill card activity</p>
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
                    <p className={`mt-1 text-sm font-medium ${stat.positive ? 'text-emerald-600' : 'text-red-600'}`}>
                      {stat.change} from last week
                    </p>
                  </div>
                ))}
              </div>

              {/* Two column layout */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {/* Recent Skill Cards */}
                <div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
                  <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                    <h2 className="font-semibold">Recent Skill Cards</h2>
                    <button
                      onClick={() => setActiveTab('cards')}
                      className="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400"
                    >
                      View all
                    </button>
                  </div>
                  <div className="divide-y divide-slate-100 dark:divide-slate-800">
                    {RECENT_CARDS.map((card) => (
                      <div key={card.id} className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <div className="min-w-0">
                          <p className="font-medium truncate">{card.title}</p>
                          <p className="text-sm text-slate-500">
                            by {card.owner} · {card.claims} claims · {card.date}
                          </p>
                        </div>
                        <span className={`ml-3 shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyles[card.status]}`}>
                          {card.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recent Users */}
                <div className="rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
                  <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 dark:border-slate-800">
                    <h2 className="font-semibold">New Users</h2>
                    <button
                      onClick={() => setActiveTab('users')}
                      className="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400"
                    >
                      View all
                    </button>
                  </div>
                  <div className="divide-y divide-slate-100 dark:divide-slate-800">
                    {RECENT_USERS.map((u) => (
                      <div key={u.id} className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                        <div className="min-w-0">
                          <p className="font-medium truncate">{u.name}</p>
                          <p className="text-sm text-slate-500 truncate">{u.email}</p>
                        </div>
                        <div className="ml-3 flex items-center gap-2">
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${roleStyles[u.role]}`}>
                            {u.role}
                          </span>
                          <span className="text-xs text-slate-400">{u.joined}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Skill Cards Tab */}
          {activeTab === 'cards' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold tracking-tight">Skill Cards</h1>
                  <p className="mt-1 text-slate-500">Review and moderate all submitted skill cards</p>
                </div>
                <div className="flex gap-2">
                  <select className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
                    <option>All statuses</option>
                    <option>Approved</option>
                    <option>Pending</option>
                    <option>Flagged</option>
                  </select>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/50 text-left">
                    <tr>
                      <th className="px-5 py-3 font-medium text-slate-500">Title</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Owner</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Claims</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Status</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Submitted</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {RECENT_CARDS.map((card) => (
                      <tr key={card.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                        <td className="px-5 py-3.5 font-medium">{card.title}</td>
                        <td className="px-5 py-3.5 text-slate-500">{card.owner}</td>
                        <td className="px-5 py-3.5">{card.claims}</td>
                        <td className="px-5 py-3.5">
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyles[card.status]}`}>
                            {card.status}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-slate-500">{card.date}</td>
                        <td className="px-5 py-3.5">
                          <div className="flex gap-2">
                            <button className="text-blue-600 hover:underline text-xs font-medium">View</button>
                            {card.status === 'pending' && (
                              <>
                                <button className="text-emerald-600 hover:underline text-xs font-medium">Approve</button>
                                <button className="text-red-600 hover:underline text-xs font-medium">Reject</button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Users Tab */}
          {activeTab === 'users' && (
            <div className="space-y-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Users</h1>
                <p className="mt-1 text-slate-500">Manage platform users and their roles</p>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/50 text-left">
                    <tr>
                      <th className="px-5 py-3 font-medium text-slate-500">Name</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Email</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Role</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Cards</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Joined</th>
                      <th className="px-5 py-3 font-medium text-slate-500">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {RECENT_USERS.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/30">
                        <td className="px-5 py-3.5 font-medium">{u.name}</td>
                        <td className="px-5 py-3.5 text-slate-500">{u.email}</td>
                        <td className="px-5 py-3.5">
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${roleStyles[u.role]}`}>
                            {u.role}
                          </span>
                        </td>
                        <td className="px-5 py-3.5">{u.cards}</td>
                        <td className="px-5 py-3.5 text-slate-500">{u.joined}</td>
                        <td className="px-5 py-3.5">
                          <button className="text-blue-600 hover:underline text-xs font-medium">Edit</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Placeholder for other tabs */}
          {['recruiters', 'reports', 'settings'].includes(activeTab) && (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <p className="text-lg font-medium">{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}</p>
              <p className="mt-1 text-sm">This section is coming soon</p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default Admin