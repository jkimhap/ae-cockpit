"""ui.py — the cockpit SPA. Stage-aware deal view with talk-track prompts,
live ROI calculator, and BANT qualification scoring. Served by serve.py."""

def html(rep):
    return TEMPLATE.replace("__REP__", rep)

TEMPLATE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quinn · SalesOS Cockpit</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#fbfbfc;--panel:#ffffff;--panel2:#f6f7f8;--ink:#17191e;--muted:#646a73;--faint:#9aa0a8;
--line:#ededf0;--line2:#e3e4e8;--accent:#17191e;--accent-soft:#eef1f3;--accent-ink:#2f6f8f;
--green:#127a4f;--green-bg:#eaf3ee;--amber:#8a6300;--amber-bg:#f4eedd;--red:#b42318;--red-bg:#fbeae9;
--shadow-sm:0 1px 2px rgba(23,25,30,.04);--shadow:0 6px 22px rgba(23,25,30,.07);
--radius:10px;--disc:#6e59c0;--disc-bg:#f1eff9;--demo:#2f6f8f;--demo-bg:#ecf2f5;--quote:#8a6300;--quote-bg:#f4eedd;
--verbal:#4f51b3;--verbal-bg:#eeeef8;--won:#127a4f;--won-bg:#eaf3ee;--lost:#b42318;--lost-bg:#fbeae9;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased;letter-spacing:-0.006em}
button{font-family:inherit;cursor:pointer;border:none;background:none;color:inherit}a{color:inherit}.tnum{font-variant-numeric:tabular-nums}
input,select,textarea{font-family:inherit;font-size:13px;color:var(--ink)}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:#dcdad4;border-radius:8px;border:3px solid var(--bg)}
.topbar{position:sticky;top:0;z-index:30;background:rgba(250,249,247,.88);backdrop-filter:blur(8px);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px;padding:12px 30px}
.brand{display:flex;align-items:center;gap:9px}.brand .dot{width:9px;height:9px;border-radius:50%;background:var(--green)}
.brand b{font-weight:600;font-size:15px;letter-spacing:-0.02em}.brand span{color:var(--faint);font-size:11px;font-weight:500}
.brand .who{margin-left:10px;padding-left:12px;border-left:1px solid var(--line2);font-size:13px;font-weight:600}
.sp{margin-left:auto}
.engine{font-size:11px;font-weight:600;padding:3px 9px;border-radius:6px;display:inline-flex;gap:6px;align-items:center;background:#fff;border:1px solid var(--line2);color:var(--faint)}
.engine .ed{width:6px;height:6px;border-radius:50%;background:currentColor}
.engine.claude{color:var(--green)}.engine.heuristic{color:var(--amber)}.engine.none{color:var(--faint)}
.cur-tag{font-size:10px;font-weight:600;color:var(--accent-ink);border:1px solid var(--accent-ink);border-radius:5px;padding:1px 6px;margin-left:7px}
.ktag{font-size:9px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--faint);border:1px solid var(--line2);border-radius:4px;padding:2px 0;width:42px;text-align:center;flex-shrink:0}
.refreshed{font-size:11.5px;color:var(--faint)}
.rfx{font-size:12.5px;font-weight:600;padding:7px 13px;border-radius:9px;background:var(--ink);color:#fff}.rfx:hover{opacity:.9}.rfx.ghost{background:var(--panel2);color:var(--ink)}.rfx[disabled]{opacity:.5;cursor:default}
.main{padding:26px 30px 90px;max-width:1180px;margin:0 auto}
.h1{font-size:23px;font-weight:600;letter-spacing:-0.025em}.sub{color:var(--muted);font-size:13px;margin-top:3px}
.grp{margin-top:26px}.grp-h{display:flex;align-items:baseline;gap:9px;margin-bottom:11px}
.grp-h .nm{font-size:12px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.grp-h .ct{font-size:12px;color:var(--faint)}
.funnel{display:grid;grid-template-columns:repeat(4,1fr) .82fr .82fr;gap:9px}
.fstage{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:14px 15px;cursor:pointer;transition:.13s;position:relative;overflow:hidden}
.fstage:hover{box-shadow:var(--shadow);transform:translateY(-1px)}.fstage.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.fstage .fb{position:absolute;left:0;top:0;height:3px;width:100%}
.fstage .lab{font-size:11.5px;font-weight:600;color:var(--muted)}.fstage .n{font-size:28px;font-weight:600;letter-spacing:-0.03em;margin-top:6px}
.fstage .arr{color:var(--faint);font-size:11.5px;margin-top:2px;font-weight:500}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:15px 16px;cursor:pointer;transition:.13s}
.card:hover{box-shadow:var(--shadow);transform:translateY(-1px)}
.card .top{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.card .co{font-weight:600;font-size:15px;letter-spacing:-0.015em;line-height:1.3}
.card .row{display:flex;align-items:center;gap:8px;margin-top:10px;flex-wrap:wrap}.card .amt{font-weight:600;font-size:13.5px}
.card .ctc{color:var(--muted);font-size:12px;margin-top:8px;line-height:1.45}
.card .prog{margin-top:11px}.card .alerts{margin-top:10px;display:flex;flex-direction:column;gap:4px}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:6px;white-space:nowrap;background:#fff;border:1px solid var(--line2);color:var(--muted)}
.chip::before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}
.st-Discovery{color:var(--disc)}.st-Demo{color:var(--demo)}.st-Quote{color:var(--quote)}.st-Verbal{color:var(--verbal)}.st-Won{color:var(--won)}.st-Lost{color:var(--lost)}
.dcs{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;padding:3px 9px;border-radius:6px;background:#fff;border:1px solid var(--line2);color:var(--faint)}.dcs .d{width:6px;height:6px;border-radius:50%;background:currentColor}
.dcs.green{color:var(--green)}.dcs.yellow{color:var(--amber)}.dcs.red{color:var(--red)}.dcs.gray{color:var(--faint)}
.flag{display:flex;align-items:center;gap:6px;font-size:11.5px;font-weight:500;padding:4px 9px;border-radius:6px;line-height:1.35;border-left:2px solid currentColor}.flag.high{background:var(--red-bg);color:var(--red)}.flag.med{background:var(--amber-bg);color:var(--amber)}
.pbar{height:5px;background:var(--panel2);border-radius:4px;overflow:hidden}.pbar i{display:block;height:100%;background:var(--accent);border-radius:4px;transition:.2s}
.pmeta{font-size:11px;color:var(--faint);margin-bottom:4px;display:flex;justify-content:space-between}
.up-row{display:flex;gap:11px;overflow-x:auto;padding-bottom:6px}
.up{min-width:230px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px;flex-shrink:0;cursor:pointer;transition:.13s}.up:hover{box-shadow:var(--shadow);transform:translateY(-1px)}
.up .when{font-size:11px;font-weight:600;color:var(--accent-ink)}.up .ti{font-weight:600;margin-top:5px;font-size:13.5px;line-height:1.3}.up .who{color:var(--muted);font-size:12px;margin-top:4px}
.toggle{font-size:12.5px;font-weight:600;color:var(--muted);cursor:pointer;display:inline-flex;gap:6px;align-items:center}.toggle:hover{color:var(--ink)}
.back{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:13px;font-weight:500;margin-bottom:14px;cursor:pointer}.back:hover{color:var(--ink)}
.dhead{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;flex-wrap:wrap}
.dhead .co{font-size:24px;font-weight:600;letter-spacing:-0.03em}.dhead .meta{color:var(--muted);font-size:12.5px;margin-top:6px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}.dhead .meta .sep{color:var(--line2)}
.ring{width:58px;height:58px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;flex-shrink:0}
.dlayout{display:grid;grid-template-columns:1fr 330px;gap:20px;margin-top:20px;align-items:start}
@media(max-width:1020px){.dlayout{grid-template-columns:1fr}}
.lk{color:var(--accent-ink);font-weight:600;font-size:12px;cursor:pointer}.lk:hover{text-decoration:underline}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:16px 17px}.panel+.panel{margin-top:13px}
.panel h3{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);margin-bottom:12px;display:flex;align-items:center;gap:8px}.panel h3 .ct{margin-left:auto;color:var(--faint);font-size:11px;font-weight:600;text-transform:none;letter-spacing:0}
/* stage accordion */
.stage{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);margin-bottom:12px;overflow:hidden}
.stage.cur{border-color:var(--line2);box-shadow:var(--shadow-sm)}
.stage-head{display:flex;align-items:center;gap:12px;padding:15px 17px;cursor:pointer}
.stage-head:hover{background:var(--panel2)}
.stage-num{width:24px;height:24px;border-radius:50%;background:var(--panel2);color:var(--muted);font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.stage.done .stage-num{background:var(--green);color:#fff}.stage.cur .stage-num{background:var(--accent);color:#fff}
.stage-tt{flex:1;min-width:0}.stage-tt .nm{font-weight:600;font-size:15px;letter-spacing:-0.01em}.stage-tt .bl{font-size:12px;color:var(--faint);margin-top:1px}
.stage-prog{text-align:right;min-width:120px}.stage-prog .n{font-size:12px;font-weight:600;color:var(--muted);margin-bottom:4px}
.stage-prog .pbar{width:120px}
.caret{color:var(--faint);font-size:13px;transition:.2s;width:14px;text-align:center}.stage.open .caret{transform:rotate(90deg)}
.stage-body{padding:4px 17px 17px;border-top:1px solid var(--line);display:none}.stage.open .stage-body{display:block}
.ritem{padding:12px 0;border-bottom:1px solid var(--line)}.ritem:last-child{border-bottom:none}
.ritem .rl{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:500}
.ritem .gate{width:6px;height:6px;border-radius:50%;background:var(--accent);flex-shrink:0}.ritem.cap .gate{background:var(--green)}
.ritem .ai-src{font-size:10px;color:var(--accent-ink);font-weight:700}
.ritem .rh{font-size:11.5px;color:var(--faint);margin-top:2px;line-height:1.4}
.ritem .rin{margin-top:8px}
/* Talk-track prompt */
.ritem .prompt{margin-top:6px;padding:7px 10px;background:var(--accent-soft);border-radius:7px;font-size:12px;color:var(--accent-ink);line-height:1.45;font-style:italic;border-left:2px solid var(--accent-ink);cursor:pointer;position:relative}
.ritem .prompt::before{content:"SAY";font-size:9px;font-weight:700;letter-spacing:.05em;font-style:normal;position:absolute;top:-8px;left:8px;background:var(--accent-soft);padding:0 4px;color:var(--accent-ink);opacity:.7}
.ritem .prompt:hover{background:var(--demo-bg)}
.rin input,.rin select,.rin textarea{width:100%;border:1px solid var(--line2);border-radius:8px;padding:8px 10px;outline:none;background:var(--panel)}
.rin input:focus,.rin select:focus,.rin textarea:focus{border-color:var(--accent)}
.rin textarea{resize:vertical;min-height:38px;line-height:1.45}
.yn{display:inline-flex;gap:6px}.yn button{padding:7px 16px;border-radius:8px;border:1px solid var(--line2);font-size:12.5px;font-weight:600;color:var(--muted)}
.yn button.on{background:var(--ink);color:#fff;border-color:var(--ink)}.yn button.on.no{background:var(--muted)}
.ai-sug{margin-top:8px;background:var(--panel2);border-left:2px solid var(--accent-ink);border-radius:0 8px 8px 0;padding:9px 11px}
.ai-sug .hd{font-size:10px;font-weight:700;color:var(--accent-ink);text-transform:uppercase;letter-spacing:.05em}
.ai-sug .vv{font-size:13px;color:var(--ink);font-weight:600;margin-top:3px}.ai-sug .ev{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.4}
.ai-sug .acts{display:flex;gap:7px;margin-top:8px;align-items:center}.ai-sug button{font-size:11.5px;font-weight:600;padding:4px 11px;border-radius:6px}.ai-sug .ok{background:var(--ink);color:#fff}.ai-sug .no{color:var(--muted)}.ai-sug .cite{margin-left:auto;font-size:10.5px}
.snotes{margin-top:14px}.snotes label{font-size:11px;font-weight:600;color:var(--faint);text-transform:uppercase;letter-spacing:.03em}
.snotes textarea{width:100%;border:1px solid var(--line2);border-radius:9px;padding:9px 11px;font-size:12.5px;resize:vertical;min-height:54px;margin-top:6px;outline:none}.snotes textarea:focus{border-color:var(--accent)}
/* BANT Score */
.bant{margin-top:14px;background:var(--disc-bg);border:1px solid var(--disc);border-radius:10px;padding:16px 17px}
.bant h4{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--disc);margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
.bant h4 .score{font-size:20px;letter-spacing:-0.02em}
.bant-row{display:grid;grid-template-columns:70px 1fr 36px;align-items:center;gap:8px;padding:5px 0}
.bant-row .lab{font-size:11.5px;font-weight:500;color:var(--muted)}
.bant-row .track{height:7px;background:rgba(110,89,192,.15);border-radius:4px;overflow:hidden}
.bant-row .track i{display:block;height:100%;border-radius:4px;background:var(--disc);transition:.3s}
.bant-row .bv{font-size:12px;font-weight:600;color:var(--disc);text-align:right;font-variant-numeric:tabular-nums}
.bant .threshold{margin-top:10px;padding-top:10px;border-top:1px solid rgba(110,89,192,.2);font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between;align-items:center}
.bant .threshold .status{font-weight:700;font-size:12px}.bant .threshold .status.pass{color:var(--green)}.bant .threshold .status.fail{color:var(--red)}
/* ROI calc */
.roi{margin-top:14px;background:linear-gradient(135deg,#f8fffe,#f3f8fc);border:1px solid var(--demo);border-radius:10px;padding:18px 17px}
.roi h4{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--demo);margin-bottom:4px;display:flex;align-items:center;gap:8px}
.roi h4 .live{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.roi .rsub{font-size:11.5px;color:var(--muted);margin-bottom:14px;line-height:1.45}
.roi-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.roi-in{display:flex;flex-direction:column;gap:3px}.roi-in label{font-size:10.5px;font-weight:500;color:var(--muted)}
.roi-in input{background:#fff;border:1px solid var(--line2);border-radius:7px;padding:8px 10px;color:var(--ink);font-size:13px;outline:none;font-weight:500}.roi-in input:focus{border-color:var(--demo);box-shadow:0 0 0 2px rgba(47,111,143,.1)}
.roi-out{margin-top:16px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px;border-top:1px solid rgba(47,111,143,.15);padding-top:14px}
.roi-out .o{text-align:center}.roi-out .o .v{font-size:20px;font-weight:700;letter-spacing:-0.02em;color:var(--ink)}.roi-out .o .l{font-size:10px;color:var(--muted);margin-top:2px;line-height:1.3}
.roi-tot{margin-top:14px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;border-top:1px solid rgba(47,111,143,.15);padding-top:14px}.roi-tot .big{font-size:26px;font-weight:700;color:var(--demo);letter-spacing:-0.02em}.roi-tot .x{font-size:12.5px;color:var(--muted)}
.roi-cp{margin-top:12px;font-size:11.5px;font-weight:600;color:#fff;background:var(--demo);padding:8px 15px;border-radius:8px}.roi-cp:hover{opacity:.9}
/* Side panels */
.bars{display:flex;flex-direction:column;gap:8px}.barrow{display:grid;grid-template-columns:92px 1fr 24px;align-items:center;gap:9px;font-size:12px}.barrow .bl{color:var(--muted)}.barrow .bv{text-align:right;font-weight:600;font-variant-numeric:tabular-nums;color:var(--muted)}
.track{height:6px;background:var(--panel2);border-radius:4px;overflow:hidden}.track i{display:block;height:100%;border-radius:4px;background:var(--accent)}
.rationale{font-size:12px;color:var(--muted);line-height:1.5;margin-top:11px;padding-top:11px;border-top:1px solid var(--line)}
.engtag{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.03em;padding:1px 6px;border-radius:10px}.engtag.claude{background:var(--green-bg);color:var(--green)}.engtag.heuristic{background:var(--amber-bg);color:var(--amber)}
.stk{display:flex;flex-wrap:wrap;gap:6px}.stk .p{background:var(--panel2);border-radius:8px;padding:5px 9px;font-size:11.5px}.stk .p b{font-weight:600}.stk .p span{color:var(--faint)}.stk .p.dm{background:var(--won-bg)}
.act{margin-top:0}.act .it{display:grid;grid-template-columns:46px 1fr;gap:11px;padding:9px 0;border-bottom:1px solid var(--line);align-items:start}.act .it:last-child{border-bottom:none}
.act .ktag{margin-top:1px}
.act .ti{font-weight:600;font-size:12.5px;line-height:1.3}.act .mt{color:var(--faint);font-size:11px;margin-top:1px}
.loss{border-color:var(--lost-bg)!important;background:var(--lost-bg)}
.pop{position:fixed;z-index:90;background:var(--panel);border:1px solid var(--line2);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px 17px;width:370px;max-height:70vh;overflow:auto;display:none}.pop.open{display:block}
.pop .pt{font-weight:600;font-size:14px;line-height:1.3}.pop .pm{color:var(--faint);font-size:11.5px;margin-top:3px}.pop .lab{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:12px 0 5px}.pop .who{font-size:12.5px;color:var(--muted)}.pop ul{margin:0;padding-left:16px}.pop li{font-size:12.5px;line-height:1.5;margin-bottom:4px}.pop .sent{font-size:12.5px;color:var(--muted);font-style:italic;line-height:1.5}
.scrim{position:fixed;inset:0;background:rgba(28,27,25,.28);z-index:95;opacity:0;pointer-events:none;transition:.2s}.scrim.on{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;height:100vh;width:520px;max-width:92vw;background:var(--panel);z-index:96;box-shadow:-8px 0 30px rgba(28,27,25,.14);transform:translateX(100%);transition:.24s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column}.drawer.on{transform:none}
.drawer .dh{padding:18px 22px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}.drawer .dh b{font-size:15px;font-weight:600}
.drawer .tabs{display:flex;gap:4px;padding:12px 16px 0;flex-wrap:wrap}.drawer .tabs button{font-size:12px;font-weight:600;color:var(--muted);padding:6px 11px;border-radius:8px}.drawer .tabs button.on{background:var(--accent-soft);color:var(--accent-ink)}
.drawer .body{padding:8px 22px 30px;overflow:auto;flex:1}
.md h1,.md h2,.md h3{font-size:14px;font-weight:600;margin:15px 0 6px}.md h1{font-size:16px}.md p{font-size:13px;line-height:1.6;margin:7px 0}.md ul{margin:7px 0;padding-left:19px}.md li{font-size:13px;line-height:1.55;margin-bottom:4px}.md strong{font-weight:600}.md code{background:var(--panel2);padding:1px 5px;border-radius:5px;font-size:12px}
.kbfab{position:fixed;right:24px;bottom:24px;z-index:80;background:var(--ink);color:#fff;font-weight:600;font-size:13px;padding:11px 17px;border-radius:30px;box-shadow:var(--shadow);display:flex;gap:8px;align-items:center}.kbfab:hover{background:#000}
.empty{color:var(--faint);font-size:13px;padding:16px;text-align:center}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:var(--ink);color:#fff;font-size:13px;font-weight:500;padding:10px 18px;border-radius:10px;box-shadow:var(--shadow);z-index:120;opacity:0;transition:.2s;pointer-events:none}.toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
.loading{display:flex;align-items:center;justify-content:center;height:60vh;color:var(--faint);gap:10px}
.spin{width:15px;height:15px;border:2px solid var(--line2);border-top-color:var(--accent);border-radius:50%;animation:sp .7s linear infinite;display:inline-block}@keyframes sp{to{transform:rotate(360deg)}}
.hide{display:none!important}
/* ===== SalesOS two-pane shell (Phase 0) ===== */
.shell{display:grid;grid-template-columns:380px 1fr;align-items:stretch;min-height:calc(100vh - 53px)}
@media(max-width:900px){.shell{grid-template-columns:1fr}.inbox{display:none}.inbox.mobile-on{display:flex}}
.inbox{display:flex;flex-direction:column;border-right:1px solid var(--line);background:var(--panel2);position:sticky;top:53px;height:calc(100vh - 53px);overflow:hidden}
.inbox-h{padding:16px 18px 12px;border-bottom:1px solid var(--line)}
.inbox-h .ti{font-size:15px;font-weight:600;letter-spacing:-0.02em;display:flex;align-items:center;gap:8px}
.inbox-h .ti .cnt{margin-left:auto;font-size:11px;font-weight:600;color:var(--faint);background:#fff;border:1px solid var(--line2);border-radius:20px;padding:2px 9px}
.inbox-h .note{font-size:11px;color:var(--faint);margin-top:6px;line-height:1.4;display:flex;gap:5px;align-items:flex-start}
.inbox-h .note b{color:var(--amber);font-weight:700}
.inbox-list{overflow-y:auto;flex:1;padding:8px 10px 24px}
.ibgrp{margin-top:10px}.ibgrp:first-child{margin-top:4px}
.ibgrp-h{display:flex;align-items:center;gap:7px;padding:6px 8px 5px;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.ibgrp-h .dotg{width:6px;height:6px;border-radius:50%}.ibgrp-h.overdue .dotg{background:var(--red)}.ibgrp-h.today .dotg{background:var(--amber)}.ibgrp-h.upcoming .dotg{background:var(--faint)}
.ibgrp-h .n{margin-left:auto;color:var(--faint);font-weight:600}
.task{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 11px;margin:6px 0;cursor:pointer;transition:.12s}
.task:hover{box-shadow:var(--shadow-sm);border-color:var(--line2);transform:translateY(-1px)}
.task.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.task .tr1{display:flex;align-items:center;gap:7px}
.tbadge{font-size:9.5px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;padding:2px 7px;border-radius:5px;white-space:nowrap;flex-shrink:0}
.tbadge.prep{background:var(--demo-bg);color:var(--demo)}
.tbadge.followup{background:var(--quote-bg);color:var(--quote)}
.tbadge.gate{background:var(--disc-bg);color:var(--disc)}
.tbadge.routing{background:var(--verbal-bg);color:var(--verbal)}
.tbadge.multi{background:var(--won-bg);color:var(--won)}
.tbadge.watch{background:var(--accent-soft);color:var(--accent-ink)}
.task .co{font-weight:600;font-size:13px;letter-spacing:-0.01em;line-height:1.25;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.task .why{font-size:11.5px;color:var(--muted);line-height:1.4;margin-top:6px}
.task .tmeta{font-size:10.5px;color:var(--faint);margin-top:6px;display:flex;gap:6px;align-items:center}
.workspace{min-width:0;overflow-x:hidden}
.workspace .main{padding:24px 30px 90px;max-width:1180px;margin:0 auto}
.ws-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;height:70vh;color:var(--faint);gap:10px;text-align:center;padding:30px}
.ws-empty .big{font-size:15px;font-weight:600;color:var(--muted)}
.ibtoggle{display:none}
@media(max-width:900px){.ibtoggle{display:inline-flex}}
.focus-flash{animation:flash 1.4s ease-out}@keyframes flash{0%{box-shadow:0 0 0 3px var(--accent-soft)}100%{box-shadow:none}}
</style></head>
<body>
<header class="topbar">
  <div class="brand"><span class="dot"></span><b>Quinn</b><span>SalesOS Cockpit</span><span class="who" id="repName">…</span></div>
  <span class="sp"></span>
  <button class="rfx ghost ibtoggle" onclick="$('#inbox').classList.toggle('mobile-on')" title="Toggle Task Inbox">☰ Inbox</button>
  <span class="engine none" id="engine">—</span><span class="refreshed" id="refreshed"></span>
  <button class="rfx" id="rbtn" onclick="refresh(false)">↻ Refresh</button>
  <button class="rfx ghost" id="rfull" onclick="refresh(true)" title="Re-pull Gong + regenerate AI">⟳ Full sync</button>
</header>
<div class="shell">
  <aside class="inbox" id="inbox">
    <div class="inbox-h">
      <div class="ti">Task Inbox <span class="cnt" id="inboxCount">—</span></div>
      <div class="note"><b>⚠</b><span>Tasks are <b style="color:var(--amber)">derived heuristically</b> from current deal state — not yet event-driven (Phase 2).</span></div>
    </div>
    <div class="inbox-list" id="inboxList"><div class="empty">Loading…</div></div>
  </aside>
  <div class="workspace"><main class="main" id="view"><div class="loading"><span class="spin"></span> Loading live HubSpot data…</div></main></div>
</div>
<div class="pop" id="pop"></div>
<button class="kbfab" onclick="openKB()">Playbook</button>
<div class="scrim" id="scrim" onclick="closeKB()"></div>
<aside class="drawer" id="drawer"><div class="dh"><b>Playbook & KB</b><button class="lk" style="margin-left:auto" onclick="closeKB()">Close</button></div>
  <div class="tabs" id="kbTabs"></div><div class="body md" id="kbBody"></div></aside>
<div class="toast" id="toast"></div>
<script>
const REP="__REP__"; let D=null;
const $=s=>document.querySelector(s);
const esc=s=>(s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=v=>v==null||v===''||isNaN(v)?'—':'$'+Math.round(+v).toLocaleString();
const dealById=id=>D.deals.find(d=>d.id===id);
const fmtDate=s=>{if(!s)return '';const d=new Date(s);return isNaN(d)?String(s).slice(0,10):d.toLocaleDateString('en-US',{month:'short',day:'numeric'});};
const fmtDT=s=>{const d=new Date(s);return isNaN(d)?s:d.toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric'})+' · '+d.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});};
const ago=s=>{if(!s)return '';const d=new Date(s.replace(' UTC','Z').replace(' ','T'));if(isNaN(d))return s;const h=(Date.now()-d)/36e5;return h<1?Math.max(1,Math.round(h*60))+'m ago':h<24?Math.round(h)+'h ago':Math.round(h/24)+'d ago';};
const openDeals=()=>D.deals.filter(d=>d.is_open);
const LS={k:id=>'cockpit:'+REP+':'+id,get(id){try{return JSON.parse(localStorage.getItem(this.k(id)))||{}}catch(e){return {}}},set(id,v){localStorage.setItem(this.k(id),JSON.stringify(v))}};
function dst(id){const s=LS.get(id);s.cap=s.cap||{};s.src=s.src||{};s.dis=s.dis||{};s.notes=s.notes||{};s.roi=s.roi||{};return s;}
function save(id,s){LS.set(id,s);}
const rubricById={};
async function fetchJSON(u,o){const url=new URL(u,location.origin);const r=await fetch(url.href,o);return r.json();}
async function load(){try{D=await fetchJSON('/api/data?rep='+REP);D.rubric.forEach(s=>s.items.forEach(it=>rubricById[it.id]=it));hydrate();route();}catch(e){$('#view').innerHTML='<div class="empty">Failed to load: '+esc(e.message)+'</div>';}}
let refreshing=false;
async function refresh(full,silent){if(refreshing)return;refreshing=true;$('#rbtn').disabled=true;$('#rfull').disabled=true;const o=$('#rbtn').textContent;$('#rbtn').textContent=full?'Full syncing…':'Refreshing…';
  try{const j=await fetchJSON('/api/refresh?rep='+REP+'&full='+(full?1:0),{method:'POST'});if(j.ok){D=j.payload;D.rubric.forEach(s=>s.items.forEach(it=>rubricById[it.id]=it));hydrate();route();if(!silent)toast((full?'Full sync':'Refreshed')+' · '+j.took+'s');}else toast('Refresh failed: '+(j.error||''));}
  catch(e){toast('Refresh failed');}finally{refreshing=false;$('#rbtn').disabled=false;$('#rfull').disabled=false;$('#rbtn').textContent=o;}}
function hydrate(){$('#repName').textContent=D.rep;$('#refreshed').textContent='HubSpot '+ago(D.refreshed);
  const e=$('#engine');e.className='engine '+(D.ai_engine||'none');e.innerHTML='<span class="ed"></span>'+(D.ai_engine==='claude'?'Claude':D.ai_engine==='heuristic'?'Heuristic':'No AI');
  e.title=D.ai_engine==='heuristic'?'Anthropic key out of credits — add credits then Full sync to upgrade to Claude':'';
  renderInbox();}
function toast(t){const el=$('#toast');el.textContent=t;el.classList.add('on');setTimeout(()=>el.classList.remove('on'),2600);}
window.addEventListener('hashchange',route);
function route(){if(!D)return;const h=location.hash||'#/';if(h.startsWith('#/deal/'))renderDeal(h.slice(7));else renderMain();window.scrollTo(0,0);}

/* ---------- LEFT PANE: SalesOS Task Inbox (Phase 0, heuristic) ----------
   Tasks are derived server-side in tasks.py from the current deal snapshot
   (payload.inbox). They are NOT event-driven yet — that's Phase 2. Clicking a
   task selects its deal in the right pane and focuses the relevant section. */
const TBADGE={'Call Prep':['prep','Prep'],'Draft Follow-up':['followup','Follow-up'],
  'Gate-Capture':['gate','Gate'],'Routing-Check':['routing','Routing'],
  'Multi-thread':['multi','Multi-thread'],'Watch':['watch','Watch']};
const BUCKET_LABEL={overdue:'Overdue',today:'Today',upcoming:'Upcoming'};
let selTask=null;          // currently selected task id
let pendingFocus=null;     // {deal_id, section, stage} to focus after renderDeal
function inboxData(){return (D&&D.inbox)||{buckets:{overdue:[],today:[],upcoming:[]},total:0};}
function renderInbox(){
  const ib=inboxData();const list=$('#inboxList');if(!list)return;
  $('#inboxCount').textContent=ib.total||0;
  let html='';
  ['overdue','today','upcoming'].forEach(b=>{
    const ts=(ib.buckets&&ib.buckets[b])||[];if(!ts.length)return;
    html+=`<div class="ibgrp"><div class="ibgrp-h ${b}"><span class="dotg"></span>${BUCKET_LABEL[b]}<span class="n">${ts.length}</span></div>${ts.map(taskRow).join('')}</div>`;
  });
  list.innerHTML=html||'<div class="empty">No open tasks — inbox clear.</div>';
}
function taskRow(t){
  const tb=TBADGE[t.type]||['watch',t.type];
  return `<div class="task ${selTask===t.id?'sel':''}" onclick="selectTask('${esc(t.id)}')">
    <div class="tr1"><span class="tbadge ${tb[0]}">${esc(tb[1])}</span><span class="co" title="${esc(t.company)}">${esc(t.company)}</span></div>
    <div class="why">${esc(t.why)}</div>
    <div class="tmeta"><span>${esc(t.title)}</span><span>·</span><span>${esc(t.owner)}</span></div></div>`;
}
function findTask(id){const ib=inboxData();for(const b of ['overdue','today','upcoming']){const t=((ib.buckets||{})[b]||[]).find(x=>x.id===id);if(t)return t;}return null;}
function selectTask(id){
  const t=findTask(id);if(!t)return;selTask=id;
  pendingFocus={deal_id:t.deal_id,section:t.section,stage:t.section_stage};
  renderInbox();
  if(location.hash==='#/deal/'+t.deal_id)route();      // already there → re-render & focus
  else location.hash='#/deal/'+t.deal_id;               // else navigate (route() fires)
}
/* After a deal renders, expand the relevant stage and scroll the section into view. */
function applyFocus(d){
  if(!pendingFocus||pendingFocus.deal_id!==d.id)return;
  const f=pendingFocus;pendingFocus=null;
  if(f.stage&&['gate','prep','followup'].includes(f.section)){openStages[d.id]=openStages[d.id]||{};openStages[d.id][f.stage]=true;renderDeal(d.id);}
  const sel={prep:'#stage-'+f.stage,gate:'#stage-'+f.stage,followup:'#stage-'+f.stage,
    stakeholders:'#panel-stakeholders',routing:'#panel-stakeholders',activity:'#panel-activity'}[f.section];
  setTimeout(()=>{const el=sel&&$(sel);if(el){el.scrollIntoView({behavior:'smooth',block:'start'});el.classList.add('focus-flash');setTimeout(()=>el.classList.remove('focus-flash'),1400);}},60);
}

/* ---------- capture helpers ---------- */
function capVal(id,iid){const s=dst(id);return s.cap[iid]!=null?s.cap[iid]:'';}
function isCap(id,iid){return capVal(id,iid)!=='';}
function stageProg(d,stage){let cap=0,tot=stage.items.length,gates=0,gmet=0;stage.items.forEach(it=>{if(isCap(d.id,it.id))cap++;if(it.gate){gates++;if(isCap(d.id,it.id))gmet++;}});return {cap,tot,gates,gmet};}
function dcsBadge(d){const s=d.dcs.score;return `<span class="dcs ${d.dcs.color}"><span class="d"></span>${s==null?'—':s}</span>`;}
function stageChip(s){return `<span class="chip st-${s}">${s}</span>`;}
function alertFlags(d){return (d.alerts||[]).slice(0,2).map(a=>`<div class="flag ${a.sev}">${esc(a.text)}</div>`).join('');}

/* ---------- main page ---------- */
const OPEN_ORDER=['Discovery','Demo','Quote','Verbal'];
function curStageObj(d){return D.rubric.find(s=>s.key===d.rubric_stage)||D.rubric[1];}
function dealCard(d){
  const cs=curStageObj(d);const pr=stageProg(d,cs);
  const pc=d.primary_contact.name?`${esc(d.primary_contact.name)}${d.primary_contact.title?' · '+esc(d.primary_contact.title):''}`:'';
  return `<div class="card" onclick="location.hash='#/deal/${d.id}'">
    <div class="top"><div class="co">${esc(d.company)}</div>${dcsBadge(d)}</div>
    <div class="row">${stageChip(d.stage)}<span class="amt tnum">${money(d.arr||d.amount)}</span>${d.dcs.days_in_stage!=null?`<span style="color:var(--faint);font-size:11.5px">${d.dcs.days_in_stage}d</span>`:''}</div>
    ${pc?`<div class="ctc">${pc}</div>`:''}
    <div class="prog"><div class="pmeta"><span>${esc(cs.name)} rubric</span><span>${pr.cap}/${pr.tot}${pr.gates?` · gates ${pr.gmet}/${pr.gates}`:''}</span></div><div class="pbar"><i style="width:${Math.round(pr.cap/pr.tot*100)}%"></i></div></div>
    ${alertFlags(d)?`<div class="alerts">${alertFlags(d)}</div>`:''}</div>`;
}
let filterStage=null;
const stColor=l=>({Won:'won',Lost:'lost',Discovery:'disc',Demo:'demo',Quote:'quote',Verbal:'verbal'}[l]||'demo');
function funnelTiles(){return D.funnel.map(f=>`<div class="fstage ${filterStage===f.stage_id?'sel':''}" onclick="toggleFunnel('${f.stage_id}')"><div class="fb" style="background:var(--${stColor(f.label)})"></div><div class="lab">${esc(f.full)}</div><div class="n tnum">${f.n}</div><div class="arr tnum">${money(f.arr)}</div></div>`).join('');}
function toggleFunnel(sid){filterStage=(filterStage===sid?null:sid);renderMain();}
function renderMain(){
  const v=$('#view');const ods=openDeals();const closed=D.deals.filter(d=>!d.is_open);
  const up=D.upcoming.length?D.upcoming.map(u=>`<div class="up" onclick="${u.deal_id?`location.hash='#/deal/${u.deal_id}'`:''}"><div class="when">${esc(fmtDT(u.start))}</div><div class="ti">${esc(u.company||u.title||'Meeting')}</div><div class="who">${u.deal_id?'Open deal':'New'}</div></div>`).join(''):'';
  let body='';
  if(filterStage){
    const f=D.funnel.find(x=>x.stage_id===filterStage);const ds=D.deals.filter(d=>d.stage_id===filterStage);
    body=`<div class="grp"><div class="grp-h"><span class="nm">${esc(f.full)}</span><span class="ct">${ds.length} · ${money(ds.reduce((s,d)=>s+(d.arr||d.amount||0),0))}</span></div><div class="grid">${ds.map(dealCard).join('')||'<div class="empty">No deals in this stage.</div>'}</div></div>`;
  }else{
    OPEN_ORDER.forEach(st=>{const ds=ods.filter(d=>d.stage===st);if(!ds.length)return;
      body+=`<div class="grp"><div class="grp-h"><span class="nm">${st}</span><span class="ct">${ds.length} · ${money(ds.reduce((s,d)=>s+(d.arr||d.amount||0),0))}</span></div><div class="grid">${ds.map(dealCard).join('')}</div></div>`;});
    if(!body)body='<div class="empty">No open deals.</div>';
    body+=`<div class="grp"><div class="grp-h"><span class="toggle" onclick="this.closest('.grp').querySelector('.cl').classList.toggle('hide');this.querySelector('b').textContent=this.querySelector('b').textContent==='+'?'–':'+'"><b>+</b> Closed (${closed.length})</span></div><div class="cl hide grid">${closed.map(dealCard).join('')||'<div class="empty">None.</div>'}</div></div>`;
  }
  v.innerHTML=`<div class="h1">Pipeline</div><div class="sub">${ods.length} open deals · ${money(ods.reduce((s,d)=>s+(d.arr||d.amount||0),0))} open pipeline</div>
    ${up?`<div class="grp"><div class="grp-h"><span class="nm">Upcoming</span></div><div class="up-row">${up}</div></div>`:''}
    <div class="grp"><div class="grp-h"><span class="nm">Funnel</span><span class="ct">${filterStage?'<a class="lk" onclick="toggleFunnel(null)">Clear filter</a>':'Click a stage to filter'}</span></div><div class="funnel">${funnelTiles()}</div></div>
    ${body}`;
}

/* ---------- deal view ---------- */
let openStages={};
function renderDeal(id){
  const d=dealById(id);const v=$('#view');if(!d){v.innerHTML='<div class="empty">Deal not found.</div>';return;}
  if(!openStages[id])openStages[id]={[d.rubric_stage]:true};
  const stagesHTML=D.rubric.map((s,i)=>stageSection(d,s,i)).join('');
  v.innerHTML=`<a class="back" onclick="location.hash='#/'">← All deals</a>
   <div class="dhead"><div><div class="co">${esc(d.company)}</div>
     <div class="meta">${stageChip(d.stage)} <span class="sep">·</span> <b class="tnum">${money(d.arr||d.amount)}</b>
       <span class="sep">·</span> ${esc(d.dealtype==='newbusiness'?'New business':d.dealtype)}${d.industry?`<span class="sep">·</span> ${esc(d.industry)}`:''}${d.employees?`<span class="sep">·</span> ${d.employees} employees`:''}
       <span class="sep">·</span> via ${esc(d.source)}${/orum/i.test(d.source)?' ☎':''}<span class="sep">·</span> <a class="lk" href="${d.hubspot_url}" target="_blank">HubSpot ↗</a></div></div>
     ${dcsBig(d)}</div>
   <div class="dlayout"><div>${d.loss?lossPanel(d):''}${stagesHTML}</div>
     <div>${dcsPanel(d)}${stakePanel(d)}${activityPanel(d)}</div></div>`;
  applyFocus(d);
}
function dcsBig(d){const c=d.dcs.color,s=d.dcs.score;const col=c==='green'?'var(--green)':c==='yellow'?'var(--amber)':c==='red'?'var(--red)':'var(--faint)';const bg=c==='green'?'var(--green-bg)':c==='yellow'?'var(--amber-bg)':c==='red'?'var(--red-bg)':'var(--panel2)';
  return `<div style="text-align:center"><div class="ring" style="background:${bg};color:${col}">${s==null?'—':s}</div><div style="font-size:10px;font-weight:600;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.03em">Confidence</div></div>`;}
function stageSection(d,s,i){
  const open=!!openStages[d.id][s.key];const cur=s.key===d.rubric_stage;const pr=stageProg(d,s);
  const done=pr.gates>0&&pr.gmet===pr.gates;
  const items=s.items.map(it=>ritem(d,it)).join('');
  const bant=s.key==='disc'?bantPanel(d):'';
  const roi=s.key==='roi'?roiCalc(d):'';
  const notes=`<div class="snotes"><label>Notes — ${esc(s.name)}</label><textarea placeholder="Capture anything for this stage…" oninput="setNote('${d.id}','${s.key}',this.value)">${esc(dst(d.id).notes[s.key]||'')}</textarea></div>`;
  return `<div class="stage ${open?'open':''} ${cur?'cur':''} ${done?'done':''}" id="stage-${s.key}">
    <div class="stage-head" onclick="toggleStage('${d.id}','${s.key}')">
      <div class="stage-num">${done?'✓':i+1}</div>
      <div class="stage-tt"><div class="nm">${esc(s.name)}${cur?' <span class="cur-tag">Current</span>':''}</div><div class="bl">${esc(s.blurb)}</div></div>
      <div class="stage-prog"><div class="n">${pr.cap}/${pr.tot} captured${pr.gates?` · gates ${pr.gmet}/${pr.gates}`:''}</div><div class="pbar"><i style="width:${Math.round(pr.cap/pr.tot*100)}%"></i></div></div>
      <div class="caret">▸</div></div>
    <div class="stage-body">${items}${bant}${roi}${notes}</div></div>`;
}
function ritem(d,it){
  const val=capVal(d.id,it.id);const cap=val!=='';const src=dst(d.id).src[it.id];
  const ai=d.ai_fields[it.id];const dis=dst(d.id).dis[it.id];
  let input='';
  if(it.type==='yesno'){input=`<div class="yn"><button class="${val==='yes'?'on':''}" onclick="setCap('${d.id}','${it.id}','yes')">Yes</button><button class="${val==='no'?'on no':''}" onclick="setCap('${d.id}','${it.id}','no')">No</button></div>`;}
  else if(it.type==='enum'){input=`<select onchange="setCap('${d.id}','${it.id}',this.value)"><option value="">—</option>${it.options.map(o=>`<option ${val===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;}
  else if(it.type==='text'){input=`<textarea rows="2" placeholder="Capture…" oninput="setCapDebounced('${d.id}','${it.id}',this.value)">${esc(val)}</textarea>`;}
  else{input=`<input type="number" placeholder="${it.type==='money'?'$ amount':'number'}" value="${esc(val)}" oninput="setCapDebounced('${d.id}','${it.id}',this.value)">`;}
  const promptHTML=it.prompt?`<div class="prompt" onclick="copyPrompt(this)" title="Click to copy">"${esc(it.prompt)}"</div>`:'';
  let aiB='';
  if(ai&&!cap&&!dis){aiB=`<div class="ai-sug"><div class="hd">AI suggestion</div><div class="vv">${esc(ai.value)}</div>${ai.evidence?`<div class="ev">${esc(ai.evidence)}</div>`:''}
    <div class="acts"><button class="ok" onclick="acceptField('${d.id}','${it.id}')">Accept</button><button class="no" onclick="dismissField('${d.id}','${it.id}')">Dismiss</button>${ai.cite&&ai.cite.gid?`<a class="lk cite" onclick="showCall('${d.id}','${ai.cite.gid}',event)">${esc(ai.cite.label)}</a>`:''}</div></div>`;}
  return `<div class="ritem ${cap?'cap':''}"><div class="rl">${it.gate?'<span class="gate"></span>':''}${esc(it.label)}${cap&&src==='ai'?' <span class="ai-src">AI</span>':''}</div>
    <div class="rh">${esc(it.hint)}</div>${promptHTML}<div class="rin">${input}</div>${aiB}</div>`;
}
function copyPrompt(el){navigator.clipboard&&navigator.clipboard.writeText(el.textContent.replace(/^"|"$/g,''));toast('Question copied');}
function toggleStage(id,k){openStages[id][k]=!openStages[id][k];renderDeal(id);}
const _t={};
function setCapDebounced(id,iid,v){clearTimeout(_t[iid]);_t[iid]=setTimeout(()=>{const s=dst(id);s.cap[iid]=v;s.src[iid]='ae';save(id,s);updateBant(id);},400);}
function setCap(id,iid,v){const s=dst(id);if(it_isyn(iid)&&s.cap[iid]===v)v='';s.cap[iid]=v;s.src[iid]='ae';save(id,s);renderDeal(id);}
function it_isyn(iid){return (rubricById[iid]||{}).type==='yesno';}
function acceptField(id,iid){const s=dst(id);s.cap[iid]=dealById(id).ai_fields[iid].value;s.src[iid]='ai';save(id,s);renderDeal(id);}
function dismissField(id,iid){const s=dst(id);s.dis[iid]=true;save(id,s);renderDeal(id);}
function setNote(id,k,v){const s=dst(id);s.notes[k]=v;save(id,s);}

/* ---------- BANT Qualification Score ---------- */
const BANT_FIELDS=[{id:'d_bant_b',label:'Budget',max:20},{id:'d_bant_a',label:'Authority',max:20},{id:'d_bant_n',label:'Need',max:40},{id:'d_bant_t',label:'Timeline',max:20}];
function bantScore(id){let total=0,filled=0;BANT_FIELDS.forEach(f=>{const v=parseFloat(capVal(id,f.id));if(!isNaN(v)&&v>0){total+=v;filled++;}});return {total,filled,max:100};}
function updateBant(id){const el=document.getElementById('bant-'+id);if(el){const d=dealById(id);if(d)el.outerHTML=bantPanel(d);}}
function bantPanel(d){
  const bs=bantScore(d.id);
  const rows=BANT_FIELDS.map(f=>{const v=parseFloat(capVal(d.id,f.id))||0;const pct=Math.round(v/f.max*100);
    return `<div class="bant-row"><div class="lab">${f.label}</div><div class="track"><i style="width:${pct}%"></i></div><div class="bv">${v}/${f.max}</div></div>`;}).join('');
  const pass=bs.total>=50;const statusCls=bs.filled===0?'':'status '+(pass?'pass':'fail');const statusTxt=bs.filled===0?'Score BANT fields above':pass?'QUALIFIED':'BELOW THRESHOLD';
  return `<div class="bant" id="bant-${d.id}"><h4>BANT Qualification<span class="score">${bs.filled?bs.total+'/100':'—'}</span></h4>${rows}
    <div class="threshold"><span>Threshold: 50/100</span><span class="${statusCls}">${statusTxt}</span></div></div>`;
}

/* ---------- ROI Calculator ---------- */
const ROI_IN=[
  ['techs','Field techs in scope','How many techs will use Quinn?'],
  ['hourly','Avg hourly cost ($)','Fully loaded cost per tech hour'],
  ['ramp_curr','Current ramp (weeks)','Weeks to full productivity today'],
  ['ramp_new','New ramp w/ Quinn (weeks)','Target ramp with Quinn training'],
  ['hires','New hires per year','Annual hiring volume'],
  ['callback','Callback/rework rate (%)','% of jobs requiring callbacks today'],
  ['callback_cost','Cost per callback ($)','Avg cost of each callback/rework'],
  ['turnover','Annual turnover (%)','% of field team leaving per year'],
  ['replace_cost','Cost to replace ($)','Hiring + ramp cost per replacement'],
];
function roiDefaults(d){return {techs:d.employees||'',hourly:45,ramp_curr:4,ramp_new:2,hires:'',callback:15,callback_cost:350,turnover:25,replace_cost:8000};}
function roiVal(d,k){const s=dst(d.id);const dv=roiDefaults(d);return s.roi[k]!=null&&s.roi[k]!==''?s.roi[k]:(dv[k]!==''?dv[k]:'');}
function setRoi(d,k,v){const s=dst(d.id);s.roi[k]=v;save(d.id,s);roiRender(d);}
function roiCompute(d){const g=k=>parseFloat(roiVal(d,k))||0;
  const rampSaved=(g('ramp_curr')-g('ramp_new'))*40*g('hourly')*g('hires');
  const callbackSaved=g('techs')*(g('callback')/100)*g('callback_cost')*12*0.3;
  const turnoverSaved=g('techs')*(g('turnover')/100)*g('replace_cost')*0.2;
  const tot=rampSaved+callbackSaved+turnoverSaved;const price=d.amount||0;const mult=price?tot/price:0;const pay=tot?price/(tot/12):0;
  return {rampSaved,callbackSaved,turnoverSaved,tot,mult,pay,price};}
function roiCalc(d){const ins=ROI_IN.map(([k,l,h])=>`<div class="roi-in"><label title="${esc(h)}">${l}</label><input type="number" value="${esc(roiVal(d,k))}" placeholder="${h}" oninput="setRoiDeb('${d.id}','${k}',this.value)"></div>`).join('');
  return `<div class="roi"><h4><span class="live"></span> ROI Calculator</h4><div class="rsub">Quinn's 3-lever value model: onboarding productivity, quality/callbacks, retention. Updates live as you fill in prospect answers.</div>
    <div class="roi-grid">${ins}</div><div id="roiout-${d.id}">${roiOut(d)}</div></div>`;}
function roiOut(d){const c=roiCompute(d);
  return `<div class="roi-out"><div class="o"><div class="v">${money(c.rampSaved)}</div><div class="l">Onboarding productivity / yr</div></div>
    <div class="o"><div class="v">${money(c.callbackSaved)}</div><div class="l">Callbacks reduced / yr</div></div>
    <div class="o"><div class="v">${money(c.turnoverSaved)}</div><div class="l">Turnover savings / yr</div></div></div>
    <div class="roi-tot"><span class="big">${money(c.tot)}/yr</span>${c.price?`<span class="x">vs ${money(c.price)} price · <b>${c.mult.toFixed(1)}× ROI</b> · ${c.pay<1?'<1':Math.round(c.pay)} mo payback</span>`:''}</div>
    <button class="roi-cp" onclick="copyRoi('${d.id}')">Copy ROI summary</button>`;
}
const _rt={};function setRoiDeb(id,k,v){clearTimeout(_rt[k]);_rt[k]=setTimeout(()=>{const d=dealById(id);const s=dst(id);s.roi[k]=v;save(id,s);const el=$('#roiout-'+id);if(el)el.innerHTML=roiOut(d);},300);}
function roiRender(d){const el=$('#roiout-'+d.id);if(el)el.innerHTML=roiOut(d);}
function copyRoi(id){const d=dealById(id);const c=roiCompute(d);const t=`${d.company} — Quinn ROI Summary\n\nOnboarding productivity: ${money(c.rampSaved)}/yr\nCallback reduction: ${money(c.callbackSaved)}/yr\nTurnover savings: ${money(c.turnoverSaved)}/yr\n\nTotal annual value: ${money(c.tot)}/yr\nQuinn investment: ${money(c.price)}/yr\nROI: ${c.mult.toFixed(1)}× · Payback: ${Math.round(c.pay)} months`;
  navigator.clipboard&&navigator.clipboard.writeText(t);toast('ROI summary copied');}

/* ---------- side panels ---------- */
function dcsPanel(d){const sc=d.dcs.scores||{};const dims=[['pain','Pain'],['champion','Champion'],['multi_threading','Multi-thread'],['buying_language','Buying lang.'],['objection_status','Objections']];
  const bars=dims.filter(x=>sc[x[0]]!=null).map(x=>`<div class="barrow"><div class="bl">${x[1]}</div><div class="track"><i style="width:${sc[x[0]]*10}%;background:${sc[x[0]]>=7?'var(--green)':sc[x[0]]>=4?'var(--amber)':'var(--red)'}"></i></div><div class="bv">${sc[x[0]]}</div></div>`).join('');
  const alerts=(d.alerts||[]).map(a=>`<div class="flag ${a.sev}" style="margin-top:6px">${esc(a.text)}</div>`).join('');
  const tag=d.ai_engine?`<span class="engtag ${d.ai_engine}">${d.ai_engine==='claude'?'Claude':'Heuristic'}</span>`:'';
  return `<div class="panel"><h3>Deal Confidence ${tag}<span class="ct">${d.dcs.score==null?'—':d.dcs.score}</span></h3>${bars?`<div class="bars">${bars}</div>`:'<div class="empty" style="padding:4px 0">No scored calls yet.</div>'}${alerts}${d.dcs.rationale?`<div class="rationale">${esc(d.dcs.rationale)}</div>`:''}</div>`;}
function stakePanel(d){if(!d.stakeholders.length)return `<div class="panel" id="panel-stakeholders"><h3>Stakeholders <span class="ct">0</span></h3><div class="empty" style="padding:4px 0">No stakeholder on file — single-threaded. Add a 2nd contact / confirm routing.</div></div>`;const ps=d.stakeholders.map(s=>{const dm=/\b(vp|chief|coo|ceo|cfo|president|owner|founder|head|director|vice)\b/i.test(s.title||'');return `<div class="p ${dm?'dm':''}"><b>${esc(s.name)}</b>${s.title?` <span>· ${esc(s.title)}</span>`:''}</div>`;}).join('');
  return `<div class="panel" id="panel-stakeholders"><h3>Stakeholders <span class="ct">${d.stakeholders.length}</span></h3><div class="stk">${ps}</div></div>`;}
function lossPanel(d){const l=d.loss;if(!l)return'';return `<div class="panel loss"><h3 style="color:var(--lost)">Loss post-mortem</h3>${l.reason?`<div style="font-size:13px;color:var(--muted);line-height:1.5"><b style="color:var(--lost)">Why:</b> ${esc(l.reason)}</div>`:''}${l.lessons?`<div style="font-size:13px;color:var(--muted);line-height:1.5;margin-top:8px"><b style="color:var(--lost)">Lesson:</b> ${esc(l.lessons)}</div>`:''}</div>`;}
function activityPanel(d){const items=(d.timeline||[]).slice(0,40);const lbl={call:'Call',email:'Email',meeting:'Meeting',note:'Note',stage:'Stage'};
  const body=items.map(it=>{const btn=it.kind==='call'?` · <a class="lk" onclick="showCall('${d.id}','${it.ref}',event)">summary</a>`:'';
    return `<div class="it"><span class="ktag">${lbl[it.kind]||'—'}</span><div><div class="ti">${esc(it.title)}</div><div class="mt">${esc(it.sub||'')}${it.sub?' · ':''}${esc(fmtDate(it.ts))}${btn}</div></div></div>`;}).join('');
  return `<div class="panel" id="panel-activity"><h3 style="cursor:pointer" onclick="this.parentNode.querySelector('.act').classList.toggle('hide');this.querySelector('.tg').textContent=this.querySelector('.tg').textContent==='+'?'–':'+'">Activity <span class="ct"><span class="tg">+</span> ${d.calls.length} calls · ${d.emails.length} emails</span></h3><div class="act hide">${body||'<div class="empty">No activity.</div>'}</div></div>`;}

/* ---------- call popover + KB ---------- */
function showCall(did,gid,e){e.stopPropagation();const d=dealById(did);const c=d.calls.find(x=>x.gid===gid);const p=$('#pop');if(!c)return;
  p.innerHTML=`<div class="pt">${esc(c.title)}</div><div class="pm">${esc(fmtDate(c.date))}${c.duration_min?' · '+c.duration_min+' min':''} · <a class="lk" href="${c.url}" target="_blank">Open in Gong ↗</a></div>
    ${c.who?`<div class="lab">Who</div><div class="who">${esc(c.who)}</div>`:''}${c.discussed&&c.discussed.length?`<div class="lab">Discussed</div><ul>${c.discussed.slice(0,6).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}${c.sentiment?`<div class="lab">Sentiment</div><div class="sent">${esc(c.sentiment)}</div>`:''}${c.next_steps&&c.next_steps.length?`<div class="lab">Next steps</div><ul>${c.next_steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}${!c.who&&!(c.discussed||[]).length?'<div class="who" style="margin-top:10px;color:var(--faint)">No AI summary yet — open in Gong, or Full sync with Claude credits.</div>':''}`;
  p.classList.add('open');const r=e.target.getBoundingClientRect?e.target.getBoundingClientRect():{left:200,bottom:200};let x=Math.min(r.left,window.innerWidth-390),y=r.bottom+8;if(y+p.offsetHeight>window.innerHeight-10)y=Math.max(10,window.innerHeight-p.offsetHeight-10);p.style.left=Math.max(10,x)+'px';p.style.top=y+'px';}
document.addEventListener('click',e=>{const p=$('#pop');if(p.classList.contains('open')&&!p.contains(e.target)&&!e.target.closest('.lk'))p.classList.remove('open');});
let kbTab=0;
function md(t){return esc(t).replace(/^### (.*)$/gm,'<h3>$1</h3>').replace(/^## (.*)$/gm,'<h2>$1</h2>').replace(/^# (.*)$/gm,'<h1>$1</h1>').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/`(.+?)`/g,'<code>$1</code>').replace(/^[\-\*] (.*)$/gm,'<li>$1</li>').replace(/(<li>[\s\S]*?<\/li>)/g,'<ul>$1</ul>').split(/\n\n+/).map(b=>b.match(/^<(h|ul)/)?b:('<p>'+b.replace(/\n/g,' ')+'</p>')).join('');}
function openKB(){$('#scrim').classList.add('on');$('#drawer').classList.add('on');renderKB();}
function closeKB(){$('#scrim').classList.remove('on');$('#drawer').classList.remove('on');}
function renderKB(){if(!D)return;$('#kbTabs').innerHTML=D.kb.map((s,i)=>`<button class="${i===kbTab?'on':''}" onclick="kbTab=${i};renderKB()">${esc(s.title)}</button>`).join('');$('#kbBody').innerHTML=D.kb.length?md(D.kb[kbTab].md):'<div class="empty">No KB.</div>';}
load();
setInterval(()=>{if(!document.hidden)refresh(false,true);},300000);
</script>
</body></html>
"""
