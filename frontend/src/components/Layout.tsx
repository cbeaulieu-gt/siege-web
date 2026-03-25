import { NavLink, Outlet } from 'react-router-dom';
import { cn } from '../lib/utils';
import { Info, Shield } from 'lucide-react';

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-md px-3 py-2 text-sm font-medium transition-colors',
    isActive
      ? 'bg-slate-100 text-slate-900'
      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
  );

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center gap-6">
            <div className="flex items-center gap-2 text-slate-900">
              <Shield className="h-5 w-5 text-violet-600" />
              <span className="font-semibold text-sm">Siege Assignments</span>
            </div>
            <div className="flex flex-1 items-center gap-1">
              <NavLink to="/sieges" className={navLinkClass}>
                Sieges
              </NavLink>
              <NavLink to="/members" className={navLinkClass}>
                Members
              </NavLink>
              <NavLink to="/post-priorities" className={navLinkClass}>
                Posts
              </NavLink>
              {/* System link pushed to the far right */}
              <div className="ml-auto">
                <NavLink
                  to="/system"
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-slate-100 text-slate-900'
                        : 'text-slate-400 hover:bg-slate-50 hover:text-slate-600',
                    )
                  }
                >
                  <Info className="h-3.5 w-3.5" />
                  System
                </NavLink>
              </div>
            </div>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
