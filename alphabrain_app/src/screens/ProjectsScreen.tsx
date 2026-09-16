import React, { useState, useEffect } from 'react';
import { mobileApi } from '../api/client';
import {
  DeliveryMapResponse,
  DeliveryMilestone,
  ExecutiveDocSummary,
  ExecutiveDocDetail,
  DelegateCredential,
  FeedbackItem,
} from '../types';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { SkeletonList } from '../components/ui/Skeleton';

type TabMode = 'delivery' | 'docs' | 'portal';

export const ProjectsScreen: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabMode>('delivery');

  // Delivery map state
  const [deliveryMap, setDeliveryMap] = useState<DeliveryMapResponse | null>(null);
  const [loadingDelivery, setLoadingDelivery] = useState(true);

  // Docs reading room state
  const [docs, setDocs] = useState<ExecutiveDocSummary[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<ExecutiveDocDetail | null>(null);
  const [loadingDocDetail, setLoadingDocDetail] = useState(false);

  // Client & Delegate state
  const [delegates, setDelegates] = useState<DelegateCredential[]>([]);
  const [feedbackList, setFeedbackList] = useState<FeedbackItem[]>([]);
  const [loadingPortal, setLoadingPortal] = useState(false);

  // Invite modal state
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState('client_viewer');
  const [grantAdmin, setGrantAdmin] = useState(false);
  const [inviteResult, setInviteResult] = useState<DelegateCredential | null>(null);

  // Client query submission modal state
  const [showQueryModal, setShowQueryModal] = useState(false);
  const [queryAuthor, setQueryAuthor] = useState('Acme Corp Executive');
  const [queryRole, setQueryRole] = useState('Client Delegate');
  const [queryTitle, setQueryTitle] = useState('');
  const [queryDesc, setQueryDesc] = useState('');
  const [submittingQuery, setSubmittingQuery] = useState(false);

  // Admin notes for verdict actions
  const [adminNotes, setAdminNotes] = useState<Record<string, string>>({});
  const [actingOnFeedback, setActingOnFeedback] = useState<string | null>(null);

  // Copy notification banner
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // Load delivery map on mount
  useEffect(() => {
    loadDeliveryData();
  }, []);

  const loadDeliveryData = () => {
    setLoadingDelivery(true);
    mobileApi
      .getDeliveryMap()
      .then((data) => {
        setDeliveryMap(data);
        setLoadingDelivery(false);
      })
      .catch((err) => {
        console.error('Failed to load delivery map:', err);
        setLoadingDelivery(false);
      });
  };

  const loadDocsData = () => {
    setLoadingDocs(true);
    mobileApi
      .listExecutiveDocs()
      .then((data) => {
        setDocs(data);
        setLoadingDocs(false);
      })
      .catch((err) => {
        console.error('Failed to load docs:', err);
        setLoadingDocs(false);
      });
  };

  const loadPortalData = () => {
    setLoadingPortal(true);
    Promise.all([mobileApi.listDelegates(), mobileApi.listFeedback()])
      .then(([delgs, fbs]) => {
        setDelegates(delgs);
        setFeedbackList(fbs);
        setLoadingPortal(false);
      })
      .catch((err) => {
        console.error('Failed to load portal data:', err);
        setLoadingPortal(false);
      });
  };

  const handleTabChange = (tab: TabMode) => {
    setActiveTab(tab);
    if (tab === 'delivery') loadDeliveryData();
    if (tab === 'docs') loadDocsData();
    if (tab === 'portal') loadPortalData();
  };

  const openDoc = (docId: string) => {
    setLoadingDocDetail(true);
    mobileApi
      .getExecutiveDoc(docId)
      .then((detail) => {
        setSelectedDoc(detail);
        setLoadingDocDetail(false);
      })
      .catch((err) => {
        console.error('Failed to read document:', err);
        setLoadingDocDetail(false);
        showToast('Failed to open document');
      });
  };

  const handleCreateInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteName.trim()) return;
    try {
      const cred = await mobileApi.createDelegateInvite({
        member_name: inviteName.trim(),
        role: grantAdmin ? 'delegated_admin' : inviteRole,
        grant_admin_access: grantAdmin,
      });
      setInviteResult(cred);
      setInviteName('');
      loadPortalData();
      showToast(`Passcode generated: ${cred.passcode}`);
    } catch (err) {
      console.error(err);
      showToast('Error generating invite');
    }
  };

  const handleSubmitQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryTitle.trim() || !queryDesc.trim()) return;
    setSubmittingQuery(true);
    try {
      const item = await mobileApi.submitFeedback({
        author_name: queryAuthor.trim(),
        author_role: queryRole,
        problem_title: queryTitle.trim(),
        problem_description: queryDesc.trim(),
      });
      setSubmittingQuery(false);
      setShowQueryModal(false);
      setQueryTitle('');
      setQueryDesc('');
      loadPortalData();
      showToast(`Ticket #${item.id.slice(3, 7)} created & analyzed by Eva!`);
    } catch (err) {
      console.error(err);
      setSubmittingQuery(false);
      showToast('Failed to submit ticket');
    }
  };

  const handleAdminVerdict = async (
    feedbackId: string,
    action: 'handover_pipeline' | 'dismiss_rejected' | 'resolve_direct'
  ) => {
    setActingOnFeedback(feedbackId);
    const notes = adminNotes[feedbackId] || '';
    try {
      const updated = await mobileApi.adminVerdictOnFeedback(feedbackId, {
        action,
        admin_notes: notes,
        reviewer_name: 'Founder / Senior Admin',
      });
      setActingOnFeedback(null);
      loadPortalData();
      if (action === 'handover_pipeline') {
        showToast(`Admitted to Orchestration Queue as ${updated.admitted_task_id || 'Task'}`);
        // Reload delivery map to reflect active queue
        loadDeliveryData();
      } else if (action === 'dismiss_rejected') {
        showToast('Query dismissed by Admin.');
      } else {
        showToast('Direct resolution recorded.');
      }
    } catch (err) {
      console.error(err);
      setActingOnFeedback(null);
      showToast('Admin verdict failed');
    }
  };

  return (
    <div className="flex-1 flex flex-col justify-between bg-white text-[#0A0A0A] min-h-[85vh] animate-screen-enter pb-16 font-sans">
      {/* Toast banner */}
      {toastMessage && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-[#0A0A0A] text-white px-4 py-2 border-2 border-[#E6391E] font-mono text-xs shadow-2xl flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-ping" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Screen Title & Segmented Control */}
      <div className="border-b-2 border-[#0A0A0A] pb-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
            DELIVERY ENGINE • LEVEL 14 SPEC
          </span>
          <span className="font-mono text-[10px] bg-zinc-100 text-zinc-700 px-2 py-0.5 border border-zinc-300 font-bold">
            P-14 COMPANION
          </span>
        </div>
        <h2 className="text-3xl font-headline font-black mt-1 text-[#0A0A0A] uppercase tracking-tight">
          Delivery Board
        </h2>

        {/* 3 Swiss Brutalist Tabs */}
        <div className="grid grid-cols-3 gap-1 mt-4 p-1 bg-zinc-100 border border-[#0A0A0A]">
          <button
            onClick={() => handleTabChange('delivery')}
            className={`py-2 text-center font-mono text-xs font-bold uppercase transition-colors ${
              activeTab === 'delivery'
                ? 'bg-[#0A0A0A] text-white shadow-sm'
                : 'text-zinc-600 hover:text-[#0A0A0A]'
            }`}
          >
            Delivery Map
          </button>
          <button
            onClick={() => handleTabChange('docs')}
            className={`py-2 text-center font-mono text-xs font-bold uppercase transition-colors ${
              activeTab === 'docs'
                ? 'bg-[#0A0A0A] text-white shadow-sm'
                : 'text-zinc-600 hover:text-[#0A0A0A]'
            }`}
          >
            Reading Room
          </button>
          <button
            onClick={() => handleTabChange('portal')}
            className={`py-2 text-center font-mono text-xs font-bold uppercase transition-colors ${
              activeTab === 'portal'
                ? 'bg-[#0A0A0A] text-white shadow-sm'
                : 'text-zinc-600 hover:text-[#0A0A0A]'
            }`}
          >
            Client Portal
          </button>
        </div>
      </div>

      {/* =================================================================== */}
      {/* TAB 1: DELIVERY MAP (AMAZON STYLE)                                   */}
      {/* =================================================================== */}
      {activeTab === 'delivery' && (
        <div className="flex-1 my-4 overflow-y-auto max-h-[65vh] space-y-4 pr-1">
          {loadingDelivery ? (
            <div className="p-8 flex flex-col items-center justify-center bg-zinc-50 border border-zinc-200 hover-lift">
              <LoadingSpinner size="md" label="Synthesizing pipeline milestones..." />
              <div className="w-full mt-4">
                <SkeletonList count={3} />
              </div>
            </div>
          ) : !deliveryMap ? (
            <div className="p-8 text-center font-mono text-xs text-zinc-400">
              Failed to load delivery telemetry.
            </div>
          ) : (
            <>
              {/* Amazon Order Status Tracker Card */}
              <div className="p-4 bg-zinc-50 border-2 border-[#0A0A0A] card-tactile shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-wider">
                    {deliveryMap.project_name}
                  </span>
                  <span className="font-mono text-xs font-black bg-[#E6391E] text-white px-2 py-0.5">
                    {deliveryMap.overall_progress_percent}% SHIPPED
                  </span>
                </div>

                {/* Big Progress Bar */}
                <div className="mt-3 w-full bg-zinc-200 h-3 border border-[#0A0A0A] overflow-hidden">
                  <div
                    className="bg-[#0A0A0A] h-full transition-all duration-700 ease-out"
                    style={{ width: `${deliveryMap.overall_progress_percent}%` }}
                  />
                </div>

                {/* Status Indicator */}
                <div className="mt-3 flex items-center justify-between text-xs font-mono">
                  <span className="text-zinc-500">
                    STAGE {deliveryMap.active_step} OF {deliveryMap.total_steps}
                  </span>
                  <span className="font-bold text-[#0A0A0A] uppercase">
                    {deliveryMap.stages[deliveryMap.active_step - 1]?.title || 'Active Pipeline'}
                  </span>
                </div>
              </div>

              {/* In-Flight Task & Worktree Radar */}
              {deliveryMap.inflight_task && deliveryMap.inflight_task.id !== 'none' && (
                <div className="p-3 bg-[#0A0A0A] text-white border-2 border-[#E6391E] space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[#E6391E] animate-ping" />
                      <span className="font-mono text-[10px] uppercase tracking-wider text-[#E6391E] font-bold">
                        In-Flight Worktree Radar
                      </span>
                    </div>
                    <span className="font-mono text-[10px] text-zinc-400">
                      TID: {deliveryMap.inflight_task.id}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold font-headline leading-tight">
                    {deliveryMap.inflight_task.title}
                  </h4>
                  <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[10px] text-zinc-300 border-t border-zinc-800">
                    <div>
                      <span className="text-zinc-500 block">BRANCH:</span>
                      <span className="font-semibold text-cyan-300">{deliveryMap.inflight_task.branch}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block">WORKER:</span>
                      <span className="font-semibold text-zinc-200">{deliveryMap.inflight_task.worker}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Amazon Vertical Milestones */}
              <div className="p-4 bg-white border-2 border-[#0A0A0A] space-y-0 relative">
                <h3 className="font-mono text-xs font-black uppercase text-zinc-500 tracking-wider mb-4">
                  Sequential Delivery Stages
                </h3>

                {deliveryMap.stages.map((stage, idx) => {
                  const isCompleted = stage.status === 'completed';
                  const isInTransit = stage.status === 'in_transit';
                  const isLast = idx === deliveryMap.stages.length - 1;

                  return (
                    <div key={stage.id} className="relative flex items-start gap-4 pb-6 last:pb-0">
                      {/* Vertical line connecting stages */}
                      {!isLast && (
                        <div
                          className={`absolute left-[13px] top-[26px] bottom-0 w-[2px] ${
                            isCompleted ? 'bg-[#0A0A0A]' : 'bg-zinc-200 border-l border-dashed border-zinc-300'
                          }`}
                        />
                      )}

                      {/* Milestone Icon Node */}
                      <div className="relative z-10 flex-shrink-0">
                        {isCompleted ? (
                          <div className="w-7 h-7 rounded-full bg-[#0A0A0A] text-white flex items-center justify-center font-bold text-xs border-2 border-[#0A0A0A]">
                            ✓
                          </div>
                        ) : isInTransit ? (
                          <div className="w-7 h-7 rounded-full bg-white text-[#E6391E] border-2 border-[#E6391E] flex items-center justify-center font-bold text-xs shadow-md">
                            <span className="w-2.5 h-2.5 rounded-full bg-[#E6391E] animate-pulse" />
                          </div>
                        ) : (
                          <div className="w-7 h-7 rounded-full bg-white text-zinc-300 border-2 border-zinc-200 flex items-center justify-center font-mono text-[10px]">
                            {stage.step_number}
                          </div>
                        )}
                      </div>

                      {/* Milestone Details */}
                      <div className="flex-1 pt-0.5">
                        <div className="flex items-center justify-between flex-wrap gap-1">
                          <h4
                            className={`text-sm font-bold uppercase tracking-tight ${
                              isCompleted
                                ? 'text-[#0A0A0A]'
                                : isInTransit
                                ? 'text-[#E6391E]'
                                : 'text-zinc-400'
                            }`}
                          >
                            {stage.title}
                          </h4>
                          <span
                            className={`font-mono text-[9px] px-1.5 py-0.5 font-bold uppercase ${
                              isCompleted
                                ? 'bg-zinc-100 text-zinc-800 border border-zinc-300'
                                : isInTransit
                                ? 'bg-[#E6391E] text-white'
                                : 'bg-zinc-50 text-zinc-400'
                            }`}
                          >
                            {stage.checkpoint_badge}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-zinc-600 leading-relaxed font-sans">
                          {stage.summary}
                        </p>
                        <div className="mt-1.5 flex items-center justify-between font-mono text-[10px] text-zinc-400">
                          <span>ACTOR: {stage.actor}</span>
                          <span className="font-semibold text-zinc-500">{stage.timestamp_label}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Delivery Telemetry Stats */}
              <div className="grid grid-cols-3 gap-2 border-t-2 border-[#0A0A0A] pt-3 font-mono text-center">
                <div className="p-2 bg-zinc-50 border border-zinc-300">
                  <span className="text-[10px] text-zinc-500 block">TOTAL TASKS</span>
                  <span className="text-sm font-black text-[#0A0A0A]">{deliveryMap.metrics?.total_tasks_tracked ?? 0}</span>
                </div>
                <div className="p-2 bg-zinc-50 border border-zinc-300">
                  <span className="text-[10px] text-zinc-500 block">MERGED</span>
                  <span className="text-sm font-black text-[#0A0A0A]">{deliveryMap.metrics?.merged_count ?? 0}</span>
                </div>
                <div className="p-2 bg-zinc-50 border border-zinc-300">
                  <span className="text-[10px] text-zinc-500 block">HEAD HASH</span>
                  <span className="text-xs font-bold text-zinc-700">{deliveryMap.metrics?.current_git_head ?? 'HEAD'}</span>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 2: READING ROOM (EXECUTIVE ARCHITECTURE & SYSTEM DESIGN)         */}
      {/* =================================================================== */}
      {activeTab === 'docs' && (
        <div className="flex-1 my-4 overflow-y-auto max-h-[65vh] space-y-4 pr-1">
          {/* Read-Only Opus Authority Notice */}
          <div className="p-3 bg-amber-50 border-2 border-amber-600 text-amber-900 font-mono text-xs leading-tight">
            <span className="font-bold block uppercase">
              ⚠️ Invariant Notice: Strict Read-Only Access
            </span>
            <span className="text-[11px] mt-1 block">
              `SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md` is authored exclusively by Claude Opus. Pro, Flash, and subagent executors hold strict read-only access.
            </span>
          </div>

          {loadingDocs ? (
            <div className="p-8 flex items-center justify-center bg-zinc-50 border border-zinc-200">
              <LoadingSpinner size="md" label="Indexing architecture documentation..." />
            </div>
          ) : docs.length === 0 ? (
            <div className="p-8 text-center font-mono text-xs text-zinc-400">
              No architectural documents indexed.
            </div>
          ) : (
            <div className="space-y-3">
              {docs.map((doc) => (
                <div
                  key={doc.doc_id}
                  onClick={() => openDoc(doc.doc_id)}
                  className="p-4 bg-white border-2 border-[#0A0A0A] hover:bg-zinc-50 cursor-pointer card-tactile transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-[9px] bg-[#0A0A0A] text-white px-2 py-0.5 uppercase font-bold">
                      {doc.category.replace('_', ' ')}
                    </span>
                    <span className="font-mono text-[10px] text-zinc-400">
                      {doc.word_count.toLocaleString()} WORDS
                    </span>
                  </div>
                  <h3 className="mt-2 text-base font-headline font-bold text-[#0A0A0A] leading-snug">
                    {doc.title}
                  </h3>
                  <p className="mt-1.5 text-xs text-zinc-600 line-clamp-2 leading-relaxed">
                    {doc.summary}
                  </p>
                  <div className="mt-3 pt-2 border-t border-zinc-200 flex items-center justify-between font-mono text-[10px] text-zinc-500">
                    <span className="truncate max-w-[200px]">AUTHOR: {doc.author}</span>
                    <span className="font-bold text-[#E6391E] flex items-center gap-1">
                      READ SPEC →
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* TAB 3: CLIENT PORTAL (DELEGATE SHARING, QUERIES & ADMIN HANDOVER)    */}
      {/* =================================================================== */}
      {activeTab === 'portal' && (
        <div className="flex-1 my-4 overflow-y-auto max-h-[65vh] space-y-5 pr-1">
          {/* Top Actions: Invite & Submit Query */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowInviteModal(true)}
              className="flex-1 py-2.5 px-3 bg-[#0A0A0A] text-white border-2 border-[#0A0A0A] font-mono text-xs font-bold uppercase hover:bg-zinc-800 transition-colors shadow-sm"
            >
              + Invite Delegate
            </button>
            <button
              onClick={() => setShowQueryModal(true)}
              className="flex-1 py-2.5 px-3 bg-white text-[#0A0A0A] border-2 border-[#0A0A0A] font-mono text-xs font-bold uppercase hover:bg-zinc-100 transition-colors shadow-sm"
            >
              + Raise Query
            </button>
          </div>

          {/* Shareable Credentials Card */}
          <div className="p-3 bg-zinc-50 border-2 border-[#0A0A0A] space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-zinc-500 uppercase font-bold tracking-wider">
                Active Client & Team Credentials
              </span>
              <span className="font-mono text-[10px] text-zinc-400">
                {delegates.length} REGISTERED
              </span>
            </div>
            <div className="space-y-2">
              {delegates.map((d) => (
                <div
                  key={d.delegate_id}
                  className="p-2 bg-white border border-zinc-300 flex items-center justify-between text-xs font-mono"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-black text-[#0A0A0A]">{d.delegate_id}</span>
                      <span
                        className={`text-[9px] px-1.5 py-0.2 font-bold uppercase ${
                          d.can_admin_verdict
                            ? 'bg-[#E6391E] text-white'
                            : 'bg-zinc-100 text-zinc-600 border border-zinc-200'
                        }`}
                      >
                        {d.can_admin_verdict ? 'ADMIN ACCESS' : d.role.replace('_', ' ')}
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-500 block truncate max-w-[200px]">
                      {d.member_name}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-xs font-bold bg-zinc-100 px-2 py-1 border border-zinc-200">
                      {d.passcode}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Client Queries & Feedback Stream */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-zinc-200 pb-1">
              <h3 className="font-mono text-xs font-black uppercase text-zinc-500 tracking-wider">
                Client Queries & Opinion Stream
              </h3>
              <span className="font-mono text-[10px] text-zinc-400">
                {feedbackList.length} TICKETS
              </span>
            </div>

            {loadingPortal ? (
              <div className="p-8 flex items-center justify-center bg-zinc-50 border border-zinc-200">
                <LoadingSpinner size="md" label="Loading client queries..." />
              </div>
            ) : feedbackList.length === 0 ? (
              <div className="p-8 text-center font-mono text-xs text-zinc-400 bg-zinc-50 border border-dashed border-zinc-300">
                No active queries or opinions raised.
              </div>
            ) : (
              feedbackList.map((item) => {
                const isPending = item.status === 'pending_admin';
                const isHandedOver = item.status === 'handed_over';
                const isRejected = item.status === 'rejected';
                const isResolved = item.status === 'resolved';

                return (
                  <div
                    key={item.id}
                    className="p-4 bg-white border-2 border-[#0A0A0A] card-tactile space-y-3 shadow-sm"
                  >
                    {/* Header with author & status */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-mono text-[9px] text-zinc-400 uppercase tracking-widest block">
                          TICKET #{item.id.slice(3, 7)} • {item.author_role}
                        </span>
                        <h4 className="text-sm font-bold font-headline text-[#0A0A0A] mt-0.5">
                          {item.problem_title}
                        </h4>
                      </div>
                      <span
                        className={`font-mono text-[9px] px-2 py-0.5 font-bold uppercase ${
                          isHandedOver
                            ? 'bg-cyan-600 text-white'
                            : isPending
                            ? 'bg-[#E6391E] text-white animate-pulse'
                            : isRejected
                            ? 'bg-zinc-200 text-zinc-600'
                            : 'bg-zinc-800 text-white'
                        }`}
                      >
                        {item.status.replace('_', ' ')}
                      </span>
                    </div>

                    {/* Problem Description */}
                    <p className="text-xs text-zinc-700 bg-zinc-50 p-2.5 border border-zinc-200 font-sans leading-relaxed">
                      {item.problem_description}
                    </p>

                    {/* Eva AI Remediation Analysis Box */}
                    {item.eva_analysis && (
                      <div className="p-3 bg-cyan-950/10 border-l-4 border-cyan-500 space-y-1">
                        <div className="flex items-center gap-1.5 font-mono text-[10px] text-cyan-900 font-bold uppercase">
                          <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-ping" />
                          <span>Eva Real-Time Diagnostic Synthesis</span>
                        </div>
                        <p className="text-xs text-cyan-950 font-sans leading-relaxed">
                          {item.eva_analysis}
                        </p>
                      </div>
                    )}

                    {/* Admin Action Bar (Strict Admin Invariant) */}
                    {isPending && (
                      <div className="p-3 bg-zinc-50 border border-zinc-300 space-y-2">
                        <span className="font-mono text-[10px] text-zinc-600 uppercase font-bold block">
                          Founder & Admin Verdict Required
                        </span>
                        <input
                          type="text"
                          placeholder="Add admin authorization or rejection notes..."
                          value={adminNotes[item.id] || ''}
                          onChange={(e) =>
                            setAdminNotes({ ...adminNotes, [item.id]: e.target.value })
                          }
                          className="w-full px-2 py-1.5 border border-zinc-400 font-mono text-xs bg-white text-[#0A0A0A] focus:outline-none focus:border-[#E6391E]"
                        />
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            disabled={actingOnFeedback === item.id}
                            onClick={() => handleAdminVerdict(item.id, 'handover_pipeline')}
                            className="flex-1 py-2 bg-[#0A0A0A] text-white font-mono text-[11px] font-bold uppercase hover:bg-zinc-800 transition-colors border border-[#0A0A0A] shadow-sm disabled:opacity-50"
                          >
                            {actingOnFeedback === item.id ? 'Handing Over...' : '⚡ Handover to Pipeline'}
                          </button>
                          <button
                            disabled={actingOnFeedback === item.id}
                            onClick={() => handleAdminVerdict(item.id, 'dismiss_rejected')}
                            className="py-2 px-3 bg-white text-zinc-700 font-mono text-[11px] font-bold uppercase border border-zinc-400 hover:bg-zinc-100 transition-colors disabled:opacity-50"
                          >
                            Dismiss / Reject
                          </button>
                          <button
                            disabled={actingOnFeedback === item.id}
                            onClick={() => handleAdminVerdict(item.id, 'resolve_direct')}
                            className="py-2 px-3 bg-zinc-200 text-zinc-800 font-mono text-[11px] font-bold uppercase hover:bg-zinc-300 transition-colors disabled:opacity-50"
                          >
                            Direct Resolve
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Post-verdict info */}
                    {isHandedOver && (
                      <div className="p-2 bg-cyan-50 border border-cyan-300 font-mono text-xs flex items-center justify-between">
                        <span className="text-cyan-900 font-bold">
                          Enqueued as Task: {item.admitted_task_id || 'Active'}
                        </span>
                        <span className="text-[10px] text-cyan-700">Autonomous Worker Dispatched</span>
                      </div>
                    )}
                    {isRejected && item.admin_notes && (
                      <div className="p-2 bg-zinc-100 border border-zinc-300 font-mono text-[11px] text-zinc-600">
                        Admin Note: {item.admin_notes}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* MODAL: DOCUMENT READER                                              */}
      {/* =================================================================== */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-3 animate-fade-in">
          <div className="bg-white border-4 border-[#0A0A0A] w-full max-w-2xl max-h-[85vh] flex flex-col justify-between shadow-2xl">
            {/* Header */}
            <div className="p-4 border-b-2 border-[#0A0A0A] bg-zinc-50 flex items-start justify-between">
              <div>
                <span className="font-mono text-[9px] bg-[#0A0A0A] text-white px-2 py-0.5 uppercase font-bold">
                  {selectedDoc.category.replace('_', ' ')} • STRICT READ-ONLY
                </span>
                <h3 className="text-lg font-headline font-bold text-[#0A0A0A] mt-1 leading-snug">
                  {selectedDoc.title}
                </h3>
                <span className="font-mono text-[10px] text-zinc-500 mt-0.5 block">
                  Author: {selectedDoc.author}
                </span>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="w-8 h-8 bg-white border-2 border-[#0A0A0A] font-bold text-sm flex items-center justify-center hover:bg-zinc-100"
              >
                ✕
              </button>
            </div>

            {/* Content Body */}
            <div className="p-4 overflow-y-auto flex-1 font-mono text-xs text-zinc-800 space-y-3 leading-relaxed bg-zinc-50">
              {/* Section Quick-Jump Pills */}
              {selectedDoc.sections.length > 0 && (
                <div className="p-2.5 bg-white border border-zinc-300 mb-3 space-y-1">
                  <span className="font-mono text-[9px] text-zinc-400 uppercase block font-bold">
                    Section Index
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {selectedDoc.sections.slice(0, 8).map((sec, idx) => (
                      <span
                        key={idx}
                        className="bg-zinc-100 text-zinc-700 px-2 py-0.5 text-[10px] border border-zinc-200"
                      >
                        {sec}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <pre className="whitespace-pre-wrap font-mono text-[11px] text-zinc-900 bg-white p-3 border border-zinc-200 overflow-x-auto leading-normal">
                {selectedDoc.content_markdown}
              </pre>
            </div>

            {/* Footer */}
            <div className="p-3 border-t-2 border-[#0A0A0A] bg-white flex items-center justify-between font-mono text-xs">
              <span className="text-zinc-500">{selectedDoc.file_path}</span>
              <button
                onClick={() => setSelectedDoc(null)}
                className="py-1.5 px-4 bg-[#0A0A0A] text-white font-bold uppercase hover:bg-zinc-800"
              >
                Close Document
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* MODAL: INVITE DELEGATE                                              */}
      {/* =================================================================== */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-3 animate-fade-in">
          <div className="bg-white border-4 border-[#0A0A0A] w-full max-w-md p-4 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-300 pb-2">
              <h3 className="font-headline font-bold text-lg uppercase text-[#0A0A0A]">
                Generate Delegate Access
              </h3>
              <button
                onClick={() => {
                  setShowInviteModal(false);
                  setInviteResult(null);
                }}
                className="font-bold text-sm"
              >
                ✕
              </button>
            </div>

            {inviteResult ? (
              <div className="p-4 bg-zinc-50 border-2 border-[#0A0A0A] space-y-3 font-mono">
                <span className="text-xs text-green-700 font-bold block uppercase">
                  ✓ Delegate Credential Active
                </span>
                <div className="p-3 bg-white border border-zinc-300 space-y-1">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">DELEGATE ID:</span>
                    <span className="font-black text-[#0A0A0A]">{inviteResult.delegate_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">PASSCODE:</span>
                    <span className="font-black text-[#E6391E]">{inviteResult.passcode}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">ROLE:</span>
                    <span className="font-bold uppercase">{inviteResult.role}</span>
                  </div>
                </div>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(
                      `AlphaBrain Access:\nID: ${inviteResult.delegate_id}\nPasscode: ${inviteResult.passcode}`
                    );
                    showToast('Credentials copied to clipboard');
                  }}
                  className="w-full py-2 bg-[#0A0A0A] text-white text-xs font-bold uppercase hover:bg-zinc-800"
                >
                  Copy Credentials
                </button>
              </div>
            ) : (
              <form onSubmit={handleCreateInvite} className="space-y-3 font-mono text-xs">
                <div>
                  <label className="text-zinc-600 block mb-1 uppercase font-bold">
                    Member / Client Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g., Jane Doe (Acme Corp)"
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    className="w-full p-2 border-2 border-[#0A0A0A] bg-white text-[#0A0A0A] focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-zinc-600 block mb-1 uppercase font-bold">Role Type</label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full p-2 border-2 border-[#0A0A0A] bg-white text-[#0A0A0A] focus:outline-none"
                  >
                    <option value="client_viewer">Client Viewer (Read status & submit queries)</option>
                    <option value="team_delegate">Team Delegate (Engineering partner)</option>
                  </select>
                </div>

                <div className="p-3 bg-zinc-50 border border-zinc-300 flex items-start gap-2">
                  <input
                    type="checkbox"
                    id="grantAdmin"
                    checked={grantAdmin}
                    onChange={(e) => setGrantAdmin(e.target.checked)}
                    className="mt-0.5"
                  />
                  <label htmlFor="grantAdmin" className="text-[11px] text-zinc-700 leading-tight">
                    <span className="font-bold block uppercase text-[#E6391E]">
                      Grant Delegated Admin Rights
                    </span>
                    Enables this delegate to authorize pipeline handovers and reject tickets.
                  </label>
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-zinc-200">
                  <button
                    type="button"
                    onClick={() => setShowInviteModal(false)}
                    className="py-2 px-3 border border-zinc-300 uppercase hover:bg-zinc-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="py-2 px-4 bg-[#0A0A0A] text-white uppercase font-bold hover:bg-zinc-800"
                  >
                    Generate ID & Passcode
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* MODAL: SUBMIT CLIENT QUERY / OPINION                                */}
      {/* =================================================================== */}
      {showQueryModal && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-3 animate-fade-in">
          <div className="bg-white border-4 border-[#0A0A0A] w-full max-w-md p-4 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-300 pb-2">
              <h3 className="font-headline font-bold text-lg uppercase text-[#0A0A0A]">
                Raise Query or Opinion
              </h3>
              <button onClick={() => setShowQueryModal(false)} className="font-bold text-sm">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmitQuery} className="space-y-3 font-mono text-xs">
              <div>
                <label className="text-zinc-600 block mb-1 uppercase font-bold">Your Name</label>
                <input
                  type="text"
                  required
                  value={queryAuthor}
                  onChange={(e) => setQueryAuthor(e.target.value)}
                  className="w-full p-2 border-2 border-[#0A0A0A] bg-white text-[#0A0A0A] focus:outline-none"
                />
              </div>

              <div>
                <label className="text-zinc-600 block mb-1 uppercase font-bold">Role Label</label>
                <input
                  type="text"
                  required
                  value={queryRole}
                  onChange={(e) => setQueryRole(e.target.value)}
                  className="w-full p-2 border-2 border-[#0A0A0A] bg-white text-[#0A0A0A] focus:outline-none"
                />
              </div>

              <div>
                <label className="text-zinc-600 block mb-1 uppercase font-bold">
                  Problem Title / Verdict Query
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Latency spike on Stage 4 live telemetry"
                  value={queryTitle}
                  onChange={(e) => setQueryTitle(e.target.value)}
                  className="w-full p-2 border-2 border-[#0A0A0A] bg-white text-[#0A0A0A] focus:outline-none"
                />
              </div>

              <div>
                <label className="text-zinc-600 block mb-1 uppercase font-bold">
                  Detailed Description & Opinion
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder="Describe the issue observed or proposed alternate architectural path..."
                  value={queryDesc}
                  onChange={(e) => setQueryDesc(e.target.value)}
                  className="w-full p-2 border-2 border-[#0A0A0A] bg-white text-[#0A0A0A] focus:outline-none font-sans text-xs"
                />
              </div>

              <div className="p-2.5 bg-cyan-50 border border-cyan-300 text-cyan-900 text-[10px] leading-tight">
                Eva will immediately perform diagnostic synthesis on submission. An authorized Admin must approve before any autonomous task is admitted.
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-zinc-200">
                <button
                  type="button"
                  onClick={() => setShowQueryModal(false)}
                  className="py-2 px-3 border border-zinc-300 uppercase hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingQuery}
                  className="py-2 px-4 bg-[#0A0A0A] text-white uppercase font-bold hover:bg-zinc-800 disabled:opacity-50"
                >
                  {submittingQuery ? 'Analyzing...' : 'Submit to Eva'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Screen Footer */}
      <div className="border-t-2 border-[#0A0A0A] pt-3 flex items-center justify-between font-mono text-xs">
        <span className="text-zinc-500">DELIVERY PIPELINE</span>
        <span className="font-bold text-[#0A0A0A]">
          {activeTab === 'delivery'
            ? 'AMAZON 7-STAGE ENGINE'
            : activeTab === 'docs'
            ? 'EXECUTIVE READING ROOM'
            : 'DELEGATE GOVERNANCE ACTIVE'}
        </span>
      </div>
    </div>
  );
};
