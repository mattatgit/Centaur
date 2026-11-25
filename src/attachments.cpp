#include "attachments.h"
#include <QBuffer>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QImageReader>
#include <QLockFile>
#include <QRegularExpression>
#include <QSaveFile>
#include <QUrl>
#include <QUrlQuery>

namespace {
constexpr int maxImage = 1024 * 1024;
const QRegularExpression hashPattern("^[a-f0-9]{64}$");
bool validLink(const QString &link) {
    if (link.size()>2048 || link.contains('\\') || link.contains(QChar::Null)) return false;
    const QUrl url(link,QUrl::StrictMode);
    static const QRegularExpression path("^/(?:file|design)/[A-Za-z0-9]+(?:/branch/[A-Za-z0-9]+)?(?:/[^/]+)?/?$");
    static const QRegularExpression node("^[0-9]+[:-][0-9]+$");
    const auto ids=QUrlQuery(url).allQueryItemValues("node-id");
    return url.isValid() && url.scheme()=="https" && (url.host()=="figma.com" || url.host()=="www.figma.com")
        && url.userInfo().isEmpty() && url.port()==-1 && !url.hasFragment()
        && path.match(url.path()).hasMatch() && !url.path().split('/').contains("..")
        && (ids.isEmpty() || (ids.size()==1 && node.match(ids.first()).hasMatch()));
}
}

QString Attachments::imagePath(const QString &project, const QJsonObject &item) {
    const auto hash=item["hash"].toString(), format=item["format"].toString();
    if (project.isEmpty() || !QDir::isAbsolutePath(project) || !hashPattern.match(hash).hasMatch() || (format!="png" && format!="jpeg")) return {};
    const QString folder=project+"/.centaur/attachments";
    if (QFileInfo(project).isSymLink() || QFileInfo(project+"/.centaur").isSymLink() || QFileInfo(folder).isSymLink()) return {};
    const auto path=folder+"/"+hash+"."+format;
    return QFileInfo(path).isSymLink() ? QString() : path;
}
QByteArray Attachments::read(const QString &project, const QJsonObject &item) {
    const auto path=imagePath(project,item);
    if (path.isEmpty() || !QFileInfo(path).isFile()) return {};
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly) || file.size()<=0 || file.size()>maxImage) return {};
    const auto bytes=file.read(maxImage+1);
    return QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()==item["hash"].toString().toLatin1() ? bytes : QByteArray();
}
namespace {
bool validImage(const QJsonObject &ref, const QByteArray &bytes) {
    if (bytes.isEmpty() || bytes.size() > maxImage ||
        QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex() != ref["hash"].toString().toLatin1())
        return false;
    QBuffer buffer;
    buffer.setData(bytes);
    buffer.open(QIODevice::ReadOnly);
    QImageReader reader(&buffer);
    const QSize size = reader.size();
    return reader.format() == ref["format"].toString().toLatin1() && !size.isEmpty() &&
        size.width() <= 8192 && size.height() <= 8192 && qint64(size.width()) * size.height() <= 16000000 &&
        !reader.read().isNull();
}

bool storeImages(const QString &project, const QMap<QString,QByteArray> &images) {
    if (images.isEmpty()) return true;
    QDir folder(project + "/.centaur/attachments");
    if (!folder.mkpath(".")) return false;
    QLockFile lock(folder.filePath(".write.lock"));
    if (!lock.tryLock(1000)) return false;
    qint64 used = 0;
    for (const auto &file : folder.entryInfoList(QDir::Files)) used += file.size();
    QStringList missing;
    for (auto it = images.cbegin(); it != images.cend(); ++it) {
        QFile existing(it.key());
        if (QFileInfo(it.key()).isSymLink()) return false;
        if (existing.exists()) {
            if (!existing.open(QIODevice::ReadOnly) || existing.size() != it.value().size() ||
                existing.read(maxImage + 1) != it.value()) return false;
        } else {
            missing.append(it.key());
            used += it.value().size();
        }
    }
    if (used > 96 * 1024 * 1024) return false;
    QStringList created;
    for (const auto &path : missing) {
        QSaveFile file(path);
        const auto &bytes = images.value(path);
        if (!file.open(QIODevice::WriteOnly) || !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner) ||
            file.write(bytes) != bytes.size() || !file.commit()) {
            for (const auto &newPath : created) QFile::remove(newPath);
            return false;
        }
        created.append(path);
    }
    return true;
}
}

bool Attachments::store(const QString &project, const QJsonObject &ref, const QByteArray &bytes) {
    const auto path = imagePath(project, ref);
    return !path.isEmpty() && validImage(ref, bytes) && storeImages(project, {{path, bytes}});
}

bool Attachments::prepare(const QString &project, const QJsonValue &items, QJsonArray &clean, QString &error,
                          const QJsonObject *incoming, QJsonObject *outgoing, const QString &draftDir) {
    if (items.isUndefined() || items.isNull()) return true;
    error = "Could not read these attachments. Check the files, available storage and attachment limits.";
    if (!items.isArray() || items.toArray().size() > 8) return false;
    QMap<QString,QByteArray> images;
    QJsonArray accepted;
    QJsonObject wire;
    qsizetype total = 0;
    for (const auto &value : items.toArray()) {
        const auto item = value.toObject();
        if (item["type"] == "figma" && validLink(item["url"].toString())) {
            accepted.append(QJsonObject{{"type","figma"}, {"url",item["url"]}, {"name",item["name"].toString().simplified().left(120)}});
            continue;
        }
        if (item["type"] != "image") return false;
        const QJsonObject ref{{"type","image"}, {"hash",item["hash"].toString()}, {"format",item["format"].toString()}};
        const auto path = imagePath(project, ref);
        const auto hash = ref["hash"].toString();
        if (path.isEmpty()) return false;
        QByteArray bytes;
        if (incoming) {
            const auto encoded = incoming->value(hash).toString();
            if (encoded.size() > 4 * ((maxImage + 2) / 3)) return false;
            bytes = QByteArray::fromBase64(encoded.toLatin1(), QByteArray::AbortOnBase64DecodingErrors);
        } else if (!draftDir.isEmpty()) {
            QFile file(QDir(draftDir).filePath(hash + "." + ref["format"].toString()));
            const QFileInfo info(file);
            if (!info.isFile() || info.isSymLink() || !file.open(QIODevice::ReadOnly)) return false;
            bytes = file.read(maxImage + 1);
        } else {
            bytes = read(project, ref);
        }
        total += bytes.size();
        if (total > 3 * maxImage || !validImage(ref, bytes)) return false;
        images.insert(path, bytes);
        if (outgoing) wire.insert(hash, QString::fromLatin1(bytes.toBase64()));
        accepted.append(ref);
    }
    if (!storeImages(project, images)) return false;
    clean = accepted;
    error.clear();
    if (outgoing) *outgoing = wire;
    return true;
}
QJsonObject Attachments::referencedImage(const QJsonObject &state,const QString &hash) {
    if (!hashPattern.match(hash).hasMatch()) return {};
    for (const auto &msg:state["messages"].toArray())
        for (const auto &v:msg.toObject()["attachments"].toArray()) {
            const auto ref=v.toObject();
            if (ref["type"]=="image" && ref["hash"]==hash) return ref;
        }
    return {};
}

QJsonObject Attachments::agentContext(const QJsonArray &messages, qsizetype messageIndex, const QString &agentName) {
    const auto message = messages.at(messageIndex).toObject();
    auto context = [](const QJsonObject &origin, const QJsonArray &refs) {
        return QJsonObject{{"attachments", refs}, {"referenceMessage", origin["id"]}, {"referenceAuthor", origin["author"]}};
    };
    const auto attached = message["attachments"].toArray();
    if (!attached.isEmpty()) return context(message, attached);

    // An address and a shared file can have the same name ("@centaur" and
    // "Centaur"). Neither a mention nor a file title authorizes a design read.
    const auto insensitive = QRegularExpression::CaseInsensitiveOption;
    const QRegularExpression address("(?<![\\w@])@" + QRegularExpression::escape(agentName) + "(?![\\w-])", insensitive);
    auto words = message["text"].toString().remove(address).simplified();
    words.remove(QRegularExpression("^[:,\\s]+"));
    static const QRegularExpression designRequest(QStringLiteral(
        R"(^(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?)"
        R"((?:read|inspect|describe|review|use|match|follow|open|look\s+at|refer\s+to|compare\s+with|what(?:'s|\s+is|\s+does)|how\s+does)\s+)"
        R"((?:(?:in|on|the|this|that|my|our|last|earlier|previous|previously|shared|attached|linked)\s+)*figma\s+(?:design|frame|node|mockup|file|link|prototype)\b)"),
        insensitive);
    static const QRegularExpression urlToken(R"(https://(?:www\.)?figma\.com/(?:design|file)/[^\s<>"\x60]+)", insensitive);
    // Pasted links normally arrive as chips. Also support a specific shared
    // URL in a plain-text request, without matching a prefix of another node.
    static const QRegularExpression urlRequest(QStringLiteral(
        R"(^(?:please\s+)?(?:(?:read|inspect|describe|review|use|open|look\s+at)\s+)?[<\x60]?https://(?:www\.)?figma\.com/(?:design|file)/)"), insensitive);
    const auto design = designRequest.match(words);
    const bool namesDesign = design.hasMatch();
    const bool wantsDesign = namesDesign || urlRequest.match(words).hasMatch();
    static const QRegularExpression imageRequest(QStringLiteral(
        R"(\b(?:the|this|that|those|these|my|your|our|previous|last|earlier|shared|attached|uploaded)\s+)"
        R"((?:(?:previously|previous|earlier|last|shared|attached|uploaded|reference)\s+)*(?:images?|photos?|screenshots?|pictures?|attachments?|uploads?|references?)\b)"
        R"(|\b(?:images?|photos?|screenshots?|pictures?|attachments?)\s+(?:from\s+earlier|(?:I|we|you)\s+(?:sent|shared|attached|uploaded))\b)"),
        insensitive);
    if (!wantsDesign && !imageRequest.match(words).hasMatch()) return context(message, {});

    QStringList urls;
    QString designName;
    if (wantsDesign) {
        auto matches = urlToken.globalMatch(words);
        while (matches.hasNext()) {
            auto url = matches.next().captured();
            while (!url.isEmpty() && QStringLiteral(".,;!)]}").contains(url.back())) url.chop(1);
            urls.append(url);
        }
        if (!namesDesign && urls.isEmpty()) return context(message, {});
        if (namesDesign) {
            static const QRegularExpression namedFile(
                R"(^\s*(?:(?:called|named)\s+["“']?([^"”'?.!]+)|["“]([^"”]+)["”]))", insensitive);
            const auto name = namedFile.match(words.mid(design.capturedEnd()));
            if (name.hasMatch()) designName = (name.captured(1) + name.captured(2)).trimmed();
        }
    }
    const QString type = wantsDesign ? QStringLiteral("figma") : QStringLiteral("image");
    for (qsizetype i = messageIndex; i-- > 0;) {
        const auto prior = messages.at(i).toObject();
        QJsonArray selected;
        for (const auto &value : prior["attachments"].toArray()) {
            const auto ref = value.toObject();
            if (ref["type"] != type) continue;
            if (!urls.isEmpty() && !urls.contains(ref["url"].toString())) continue;
            if (!designName.isEmpty() && designName.compare(ref["name"].toString(), Qt::CaseInsensitive) != 0) continue;
            selected.append(ref);
        }
        if (!selected.isEmpty()) return context(prior, selected);
    }
    return context(message, {});
}
