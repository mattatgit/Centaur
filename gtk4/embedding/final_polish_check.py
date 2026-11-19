"""Disposable native Invite layout, clipboard and modal hover check."""
from types import MethodType, SimpleNamespace

from gi.repository import Gtk
from PIL import Image

from shell import Centaur


def check_invite(driver, folder, window, root, header, settle, move, capture, bounds, offset):
    requests=[]
    owner=SimpleNamespace(window=window,root_overlay=root,top=header,active_form=None,targets={},
                          service=SimpleNamespace(send=lambda *args,**fields:requests.append((args,fields))),
                          clear=Centaur.clear)
    owner.dialog=MethodType(Centaur.dialog,owner)
    owner.dismiss_dialog=MethodType(Centaur.dismiss_dialog,owner)
    code='centaur2:'+('zGZs4f32d67_Hp9k-'*190)
    Centaur.invite(owner)
    dialog=owner.active_form
    try:
        settle()
        field=owner.invite_code
        assert not field.copy_button.get_sensitive()
        assert window.get_focus()==owner.invite_done
        assert requests==[(('invite',),{'address':'iroh'})]
        Centaur.invitation_dialog(owner,code)
        settle()
        assert window.get_focus()==field.copy_button
        done=dialog.content.get_last_child().get_last_child()
        cancel=done.get_prev_sibling()
        x,y,w,h=bounds(done)

        def dark_width(name):
            with Image.open(folder/(name+'.png')) as source:
                row=source.convert('RGB').crop((round(x+offset[0]-4),round(y+offset[1]+h/2),
                                               round(x+offset[0]+w+4),round(y+offset[1]+h/2)+1))
                pix=list(row.getdata())
            ink=[i for i,p in enumerate(pix) if p==(23,23,23)]
            return ink[-1]-ink[0]+1

        def check_row(width):
            assert bounds(dialog.content)[2]==width
            assert field.caption.get_layout().is_ellipsized()
            assert field.caption.get_text()==field.code==code
            tx,ty,tw,th=bounds(field.caption)
            bx,by,bw,bh=bounds(field.copy_button)
            fx,fy,fw,fh=bounds(field)
            assert bx-(tx+tw)>=7 and abs((fx+fw)-(bx+bw)-8)<=1
            assert bh==24 and fh==40
            return bx,by,bw,bh

        move(60,180); normal=check_row(408)
        capture('invite-code-default')
        neighbor=bounds(cancel); allocation=(done.get_width(),done.get_height())
        move(x+w/2,y+h/2); capture('invite-done-hover')
        assert dark_width('invite-done-hover')>=dark_width('invite-code-default')+2
        assert bounds(cancel)==neighbor and (done.get_width(),done.get_height())==allocation

        bx,by,bw,bh=normal
        move(bx+bw/2,by+bh/2); capture('invite-copy-hover')
        driver.seat_command('left press'); settle(.13)
        assert field.copy_button.get_state_flags() & Gtk.StateFlags.ACTIVE
        driver.seat_command('left release'); settle(.16)
        assert field.copy_button.centaur_label.get_text()=='Copied'
        assert field.copy_button.has_css_class('copied')
        clipboard=window.get_clipboard(); result=[]
        clipboard.read_text_async(None,lambda board,reply:result.append(board.read_text_finish(reply)))
        capture('invite-code-copied')
        assert result==[code], 'The clipboard did not receive the complete code'
        assert bounds(field.caption)[2]==normal[0]-bounds(field.caption)[0]-8
        assert len(requests)==1, 'Copy generated a new invitation'
        settle(1.8)
        assert field.copy_button.centaur_label.get_text()=='Copy' and not field.copy_button.has_css_class('copied')

        move(60,180)
        dialog.limit.maximum=328; dialog.limit.queue_resize(); settle()
        check_row(328); capture('invite-code-narrow')
    finally:
        owner.dismiss_dialog(dialog)
    return 'invite-native-ellipsize-normal-narrow-full-clipboard-acknowledgement-and-modal-hover'
