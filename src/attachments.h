#pragma once
#include <QJsonArray>
#include <QJsonObject>
#include <QString>

// Only content hashes and validated Figma URLs are stored in chat history.
// A blob is always relative to an already authenticated project's directory.
namespace Attachments {
QString imagePath(const QString &project, const QJsonObject &item);
QByteArray read(const QString &project, const QJsonObject &item);
bool store(const QString &project, const QJsonObject &item, const QByteArray &bytes);
bool prepare(const QString &project, const QJsonValue &items, QJsonArray &clean, QString &error,
             const QJsonObject *incoming = nullptr, QJsonObject *outgoing = nullptr, const QString &draftDir = {});
QJsonObject referencedImage(const QJsonObject &state, const QString &hash);
}
