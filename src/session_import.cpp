// Source import is host-owned, persistent and deliberately separate from app
// validation/execution. Workers never receive shell commands from the agent.
#include "session.h"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QUuid>

static QString importRoot(const Workspace &workspace, const QString &id) {
    const auto storage=workspace.load(id)["import"].toObject()["storage"].toString();
    static const QRegularExpression valid("^[a-f0-9-]{36}$");
    return workspace.projectPath(id) + "/.centaur/import" + (valid.match(storage).hasMatch() ? "/"+storage : QString());
}

void Session::queueImport(QJsonObject &state, const QString &text, const QString &author) {
    auto queue = state["agentQueue"].toArray();
    queue.append(QJsonObject{{"id", QUuid::createUuid().toString(QUuid::WithoutBraces)},
        {"author", author}, {"text", text}, {"import", true}});
    state["agentQueue"] = queue;
    auto info = state["import"].toObject(); info["status"] = "investigating"; state["import"] = info;
}

bool Session::correctImportBranch(const QString &id, QJsonObject &state, const QString &text, const QString &author) {
    if (state.value("import").toObject()["sourceType"]!="github") return false;
    auto words=text;
    const auto mention="@"+state["agentName"].toString();
    if (words.startsWith(mention,Qt::CaseInsensitive)) words=words.mid(mention.size()).trimmed();
    static const QRegularExpression first("^(?:please\\s+)?(?:use|switch\\s+to|change\\s+to)\\s+(?:the\\s+)?[`\"']?([^\\s`\"']+?)[`\"']?\\s+branch[.!]?$",QRegularExpression::CaseInsensitiveOption);
    static const QRegularExpression second("^(?:please\\s+)?(?:use|switch\\s+to)\\s+(?:the\\s+)?branch\\s+[`\"']?([^\\s`\"']+?)[`\"']?[.!]?$",QRegularExpression::CaseInsensitiveOption);
    auto match=first.match(words); if (!match.hasMatch()) match=second.match(words);
    if (!match.hasMatch()) return false;
    if (m_imports.contains(id) || m_validatingProject==id) {
        addMessage(state,state["agentName"].toString(),"The current source operation is still finishing. Please choose the branch again once it finishes.","agent");
        persist(id,state); publish(id); return true;
    }
    if (m_agentProject==id && m_agent.busy()) { m_agent.cancel(); m_agentProject.clear(); m_agentAuthor.clear(); }
    state.remove("activeRequest"); state["agentQueue"]=QJsonArray();
    auto source=state["importLocal"].toObject()["source"].toObject(); source["branch"]=match.captured(1);
    if (!persist(id,state)) return true;
    // This authenticated chat command changes only a GitHub ref on its owning
    // host. It never forwards a guest filesystem path or grants remote import.
    importCommand({{"type","retryImport"},{"projectId",id},{"author",author},{"source",source}},nullptr);
    return true;
}

bool Session::importCommand(const QJsonObject &command, QIODevice *sender) {
    const auto type = command["type"].toString();
    if (type != "importProject" && type != "retryImport" && type != "runImport") return false;
    auto fail = [this, sender](const QString &message) { reply(sender, {{"type", "error"}, {"message", message}}); };
    // Creation and local folder paths are local-only. A guest importing from
    // Projects creates a project on THEIR local host, never on the remote host.
    if (sender && !m_peers.contains(qobject_cast<QLocalSocket *>(sender))) {
        fail("Import source on the computer that owns it, then invite collaborators."); return true;
    }
    auto id = command["projectId"].toString();
    auto state = m_workspace.load(id);
    const auto author = command["author"].toString().trimmed().left(50);
    if (author.isEmpty()) { fail("Choose your name before importing."); return true; }
    if (type == "importProject" || type == "retryImport") {
        if (type == "retryImport" && (state.value("import").toObject().isEmpty() || m_imports.contains(id)
            || m_validatingProject==id || (m_agent.busy() && m_agentProject==id))) {
            fail("Wait for the current import work to finish, then change its source."); return true;
        }
        auto source = command["source"].toObject();
        if (source.isEmpty()) source = state["importLocal"].toObject()["source"].toObject();
        auto location = source["location"].toString().trimmed();
        const auto sourceType = source["type"].toString();
        static const QRegularExpression github("^https://github\\.com/[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*(?:/tree/[^?#\\s]+)?/?$");
        if ((sourceType == "github" && !github.match(location).hasMatch())
            || (sourceType == "folder" && (!QDir::isAbsolutePath(location) || !QFileInfo(location).isDir()))
            || (sourceType != "github" && sourceType != "folder")) {
            fail("Choose a local project folder or enter a GitHub repository URL without credentials."); return true;
        }
        const auto branch=source["branch"].toString().trimmed();
        source = {{"type", sourceType}, {"location", location}};
        if (sourceType=="github" && !branch.isEmpty()) source["branch"]=branch;
        if (type == "importProject") {
            QString error;
            id = m_workspace.createProject(command["name"].toString(), "Imported project", &error, "gtk4-v1", true);
            if (id.isEmpty()) { fail(error); return true; }
            state = m_workspace.load(id);
            state["import"] = QJsonObject{{"instructions", command["instructions"].toString().left(12000)},
                {"author", author}, {"previewReady", false}};
            addMessage(state, author, command["instructions"].toString().trimmed().isEmpty()
                ? "Import this project." : command["instructions"].toString().left(12000));
        }
        auto info = state["import"].toObject();
        if (type=="retryImport") {
            auto attempts=state["importAttempts"].toArray(); attempts.append(info);
            while (attempts.size()>50) attempts.removeFirst(); state["importAttempts"]=attempts;
        }
        info["status"] = "fetching"; info["previewReady"]=false;
        info["author"]=author;
        state["epoch"]=state["epoch"].toInt()+1; state["agentQueue"]=QJsonArray(); state["proposal"]=QJsonObject();
        info["storage"]=QUuid::createUuid().toString(QUuid::WithoutBraces);
        info.remove("output"); info.remove("framework"); info["inspectionRounds"]=0;
        info["sourceType"] = sourceType; info["sourceName"] = QFileInfo(location).fileName();
        if (sourceType=="github") { info["sourceUrl"]=location; info["branch"]=branch; }
        for (const auto &key:{"commit","repository","directory"}) info.remove(key);
        state["import"] = info;
        state["importLocal"] = QJsonObject{{"source", source}};
        addMessage(state, state["agentName"].toString(), "I’ll make a separate copy and take a look. Your original project stays untouched.", "agent");
        if (!persist(id, state)) return true;
        publish(id);
        if (type == "importProject") reply(sender, {{"type", "created"}, {"projectId", id}});
        importJob(id, "acquire", {{"source", source}});
    } else {
        const auto info = state["import"].toObject();
        if (state.isEmpty() || info["status"] != "readyToRun" || updateBlocked()) {
            fail("Wait for the current work to finish before running this preview."); return true;
        }
        // Only an explicit LOCAL run action crosses from static inspection to
        // executing native code with this user's permissions.
        QFile candidate(importRoot(m_workspace,id) + "/candidate.gtk.json");
        if (!candidate.open(QIODevice::ReadOnly)) { fail("That preview is unavailable. Ask Centaur to prepare it again."); return true; }
        state["proposal"] = QJsonObject{{"kind", "proposal"}, {"gtk", QJsonDocument::fromJson(candidate.readAll()).object()},
            {"message", "Import preview"}, {"conflict", QJsonValue::Null}, {"accepted", QJsonArray{author}},
            {"authors",QJsonArray{author}},{"requestedBy",author},{"epoch",state["epoch"]}};
        m_activeRequest = {}; if (persist(id,state)) applyProposal(id, state); publish(id);
    }
    return true;
}

void Session::importJob(const QString &id, const QString &mode, QJsonObject payload) {
    if (m_imports.contains(id)) return;
    const auto executable = qEnvironmentVariable("CENTAUR_GTK_IMPORT_TOOL");
    if (executable.isEmpty()) { importResult(id,mode,{{"ok",false},{"message","The source importer is unavailable. Update Centaur and retry."}}); return; }
    auto *process = new QProcess(this); m_imports[id] = process;
    const int epoch=m_workspace.load(id)["epoch"].toInt();
    auto output = std::make_shared<QByteArray>();
    auto done = std::make_shared<bool>(false);
    auto finish = [this,id,mode,process,output,done,epoch](bool started) {
        if (*done) return; *done = true;
        *output += process->readAllStandardOutput();
        m_imports.remove(id);
        const auto result = QJsonDocument::fromJson(*output).object();
        importResult(id,mode,started && !result.isEmpty() ? result : QJsonObject{{"ok",false},
            {"message","The import was interrupted. Your source is unchanged; please retry."}},epoch);
        process->deleteLater();
    };
    connect(process,&QProcess::readyReadStandardOutput,this,[process,output] {
        *output += process->readAllStandardOutput();
        if (output->size()>2*1024*1024) process->kill();
    });
    connect(process,&QProcess::readyReadStandardError,this,[process] { process->readAllStandardError(); });
    connect(process,&QProcess::errorOccurred,this,[finish](QProcess::ProcessError error) { if (error==QProcess::FailedToStart) finish(false); });
    connect(process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[finish](int,QProcess::ExitStatus) { finish(true); });
    payload["root"] = importRoot(m_workspace,id); payload["mode"] = mode;
    process->start(executable, {});
    process->write(QJsonDocument(payload).toJson(QJsonDocument::Compact)); process->closeWriteChannel();
    publish(id); // Expose the updater's busy gate while acquisition is running.
    QTimer::singleShot(120000,process,[process] {
        if (process->state()!=QProcess::NotRunning) {
            process->terminate(); QTimer::singleShot(2000,process,[process] { if (process->state()!=QProcess::NotRunning) process->kill(); });
        }
    });
}

void Session::importResult(const QString &id, const QString &mode, const QJsonObject &result, int epoch) {
    auto state = m_workspace.load(id); if (state.isEmpty()) return;
    auto info = state["import"].toObject(); auto local = state["importLocal"].toObject();
    if ((mode=="stage" || mode=="bundle") && epoch>=0 && state["epoch"].toInt()!=epoch) {
        info["status"]="investigating"; state["import"]=info;
        persist(id,state); publish(id); QTimer::singleShot(0,this,&Session::nextRequest); return;
    }
    QFile log(m_workspace.projectPath(id)+"/.centaur/import-debug.jsonl");
    if (log.open(QIODevice::WriteOnly|QIODevice::Append)) log.write(QJsonDocument(QJsonObject{{"time",Workspace::now()},
        {"operation",mode},{"ok",result["ok"]},{"fileCount",result["fileCount"]}}).toJson(QJsonDocument::Compact)+'\n');
    if (!result["ok"].toBool()) {
        info["status"] = "failed";
        addMessage(state,state["agentName"].toString(),result["message"].toString("I couldn’t finish that import. Please retry."),"system");
    } else if (mode == "acquire") {
        if (info["sourceType"]=="github") {
            if (result["branch"].toString().isEmpty() || result["commit"].toString().isEmpty()) {
                info["status"]="failed"; state["import"]=info;
                addMessage(state,state["agentName"].toString(),"I couldn’t verify the selected branch. Please check it and retry.","system");
                persist(id,state); publish(id); return;
            }
            for (const auto &key:{"repository","sourceUrl","branch","commit","directory"}) info[key]=result[key];
            auto source=local["source"].toObject(); source["branch"]=result["branch"]; local["source"]=source;
        }
        local["context"] = QJsonObject{{"paths",result["paths"]},{"files",result["files"]},{"inventoryTruncated",result["inventoryTruncated"]}};
        info["framework"] = result["framework"]; info["fileCount"] = result["fileCount"]; info["omitted"] = result["omitted"];
        if (result["candidate"].toBool() && info["instructions"].toString().trimmed().isEmpty()) {
            info["status"] = "readyToRun";
            addMessage(state,state["agentName"].toString(),"I found a compatible GTK4 app. Run preview when you’re ready; it will run with your account’s permissions.","agent");
        } else {
            state["import"] = info;
            queueImport(state,"Investigate the imported source. Follow these instructions if supplied: " + info["instructions"].toString(),info["author"].toString());
            info = state["import"].toObject();
            addMessage(state,state["agentName"].toString(),info["sourceType"]=="github"
                ? "I found the “"+info["branch"].toString()+"” branch. I’ll use that source."
                : "The source is copied. I’m checking how it’s organised.","agent");
        }
    } else if (mode == "read") {
        const auto contextKey=result["scope"]=="adaptation" ? QString("adaptation") : QString("context");
        auto context = local[contextKey].toObject(); auto files = context["files"].toObject();
        const auto incoming = result["files"].toObject();
        for (auto it=incoming.begin(); it!=incoming.end(); ++it) files[it.key()] = it.value();
        context["files"] = files;
        if (QJsonDocument(context).toJson(QJsonDocument::Compact).size()>160000) {
            info["status"] = "awaitingAnswer";
            addMessage(state,state["agentName"].toString(),"I’ve reached the inspection limit for this step. Which part should we focus on?","agent");
        } else {
            local[contextKey] = context; state["import"] = info;
            queueImport(state,"Continue using the newly inspected files.",info["requestAuthor"].toString(info["author"].toString())); info=state["import"].toObject();
        }
    } else if (mode == "bundle") {
        info["status"] = "readyToRun";
        addMessage(state,state["agentName"].toString(),"The GTK4 preview is prepared separately from your source. Run preview when you’re ready; it runs with your account’s permissions.","agent");
    } else if (mode == "stage") {
        info["status"] = "awaitingAnswer"; info["output"] = result["output"]; info["target"] = result["target"];
        local["adaptation"]=result["inspection"];
        addMessage(state,state["agentName"].toString(),"The separate adaptation is saved. This runtime cannot be previewed in Centaur yet. Your original source is preserved.","agent");
    }
    state["import"] = info; state["importLocal"] = local;
    persist(id,state); publish(id); QTimer::singleShot(0,this,&Session::nextRequest);
}
